"""FastAPI router for the HARVEST stage (F-2.4, F-2.5, F-2.11).

Endpoints:
  POST /v1/harvest/{inference_id}       — trigger harvest on all approved sources
  GET  /v1/harvest/{inference_id}/status — harvest progress summary
  POST /v1/retrieve                      — hybrid vector + text search
"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

import src.config as cfg
from src.db.session import get_db
from src.loop.infer.repository import get_harvest_sources, get_inference
from .pipeline import harvest_source
from .repository import count_chunks, text_search, vector_search

router = APIRouter(prefix="/v1", tags=["harvest"])


class RetrieveRequest(BaseModel):
    inference_id: uuid.UUID
    query: str
    top_k: int = 5
    hybrid: bool = True


class HarvestStartResponse(BaseModel):
    status: str
    inference_id: uuid.UUID
    sources_queued: int


class SourceStatus(BaseModel):
    source_id: uuid.UUID
    url: str
    status: str
    chunks_count: int
    error: str | None


class HarvestStatusResponse(BaseModel):
    inference_id: uuid.UUID
    total_chunks: int
    sources: list[SourceStatus]


class SearchResult(BaseModel):
    content: str
    score: float


class RetrieveResponse(BaseModel):
    results: list[SearchResult]
    total_chunks: int


@router.post("/harvest/{inference_id}", status_code=202, response_model=HarvestStartResponse)
async def trigger_harvest(
    inference_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HarvestStartResponse:
    inference = await get_inference(db, inference_id)
    if inference is None:
        raise HTTPException(status_code=404, detail="Inference not found")
    if inference.status != "done":
        raise HTTPException(status_code=409, detail=f"Inference not done (status={inference.status})")

    sources = await get_harvest_sources(db, inference_id)
    approved = [s for s in sources if s.status == "approved"]
    if not approved:
        raise HTTPException(status_code=409, detail="No approved sources to harvest")

    background_tasks.add_task(
        _harvest_all_background,
        inference_id=inference_id,
        source_ids=[(s.id, s.url) for s in approved],
    )
    return HarvestStartResponse(
        status="accepted", inference_id=inference_id, sources_queued=len(approved)
    )


@router.get("/harvest/{inference_id}/status", response_model=HarvestStatusResponse)
async def get_harvest_status(
    inference_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HarvestStatusResponse:
    inference = await get_inference(db, inference_id)
    if inference is None:
        raise HTTPException(status_code=404, detail="Inference not found")

    sources = await get_harvest_sources(db, inference_id)
    total_chunks = await count_chunks(db, inference_id)

    return HarvestStatusResponse(
        inference_id=inference_id,
        total_chunks=total_chunks,
        sources=[
            SourceStatus(
                source_id=s.id,
                url=s.url,
                status=s.status,
                chunks_count=s.chunks_count,
                error=s.error,
            )
            for s in sources
        ],
    )


@router.post("/retrieve", response_model=RetrieveResponse)
async def retrieve(
    body: RetrieveRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RetrieveResponse:
    inference = await get_inference(db, body.inference_id)
    if inference is None:
        raise HTTPException(status_code=404, detail="Inference not found")

    total_chunks = await count_chunks(db, body.inference_id)
    if total_chunks == 0:
        return RetrieveResponse(results=[], total_chunks=0)

    raw_results: list[dict[str, object]]
    if body.hybrid:
        try:
            from src.loop.harvest.embedder import embed_texts
            query_embeddings = await embed_texts([body.query], input_type="query")
            vec_results = await vector_search(
                db, body.inference_id, query_embeddings[0], top_k=body.top_k * 2
            )
        except RuntimeError:
            vec_results = []

        text_results = await text_search(
            db, body.inference_id, body.query, top_k=body.top_k * 2
        )

        merged: dict[str, dict[str, object]] = {}
        for r in vec_results:
            merged[r["chunk_id"]] = {
                "content": r["content"],
                "score": cfg.HYBRID_VECTOR_WEIGHT * float(r["score"]),
            }
        for r in text_results:
            cid = r["chunk_id"]
            if cid in merged:
                merged[cid]["score"] = float(merged[cid]["score"]) + cfg.HYBRID_TEXT_WEIGHT * float(r["score"])
            else:
                merged[cid] = {
                    "content": r["content"],
                    "score": cfg.HYBRID_TEXT_WEIGHT * float(r["score"]),
                }

        raw_results = sorted(merged.values(), key=lambda x: float(x["score"]), reverse=True)[: body.top_k]  # type: ignore[assignment]
    else:
        try:
            from src.loop.harvest.embedder import embed_texts
            query_embeddings = await embed_texts([body.query], input_type="query")
            raw_results = await vector_search(  # type: ignore[assignment]
                db, body.inference_id, query_embeddings[0], top_k=body.top_k
            )
        except RuntimeError:
            raw_results = await text_search(db, body.inference_id, body.query, top_k=body.top_k)  # type: ignore[assignment]

    return RetrieveResponse(
        results=[SearchResult(content=str(r["content"]), score=float(r["score"])) for r in raw_results],
        total_chunks=total_chunks,
    )


async def _harvest_all_background(
    inference_id: uuid.UUID,
    source_ids: list[tuple[uuid.UUID, str]],
) -> None:
    from src.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        for source_id, url in source_ids:
            await harvest_source(db, source_id, url, inference_id)
