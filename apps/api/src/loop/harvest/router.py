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


@router.post("/harvest/{inference_id}", status_code=202)
async def trigger_harvest(
    inference_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
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
    return {"status": "accepted", "inference_id": str(inference_id), "sources_queued": len(approved)}


@router.get("/harvest/{inference_id}/status")
async def get_harvest_status(
    inference_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    inference = await get_inference(db, inference_id)
    if inference is None:
        raise HTTPException(status_code=404, detail="Inference not found")

    sources = await get_harvest_sources(db, inference_id)
    total_chunks = await count_chunks(db, inference_id)

    return {
        "inference_id": str(inference_id),
        "total_chunks": total_chunks,
        "sources": [
            {
                "source_id": str(s.id),
                "url": s.url,
                "status": s.status,
                "chunks_count": s.chunks_count,
                "error": s.error,
            }
            for s in sources
        ],
    }


@router.post("/retrieve")
async def retrieve(
    body: RetrieveRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    inference = await get_inference(db, body.inference_id)
    if inference is None:
        raise HTTPException(status_code=404, detail="Inference not found")

    total_chunks = await count_chunks(db, body.inference_id)
    if total_chunks == 0:
        return {"results": [], "total_chunks": 0}

    if body.hybrid:
        # Hybrid: vector + BM25 text search, deduplicated and re-ranked
        try:
            from src.loop.harvest.embedder import embed_texts
            query_embeddings = await embed_texts([body.query])
            vec_results = await vector_search(db, body.inference_id, query_embeddings[0], top_k=body.top_k * 2)
        except RuntimeError:
            vec_results = []

        text_results = await text_search(db, body.inference_id, body.query, top_k=body.top_k * 2)

        # Merge by chunk_id, weighted average score (0.7 vector + 0.3 text)
        merged: dict[str, dict] = {}
        for r in vec_results:
            merged[r["chunk_id"]] = {"content": r["content"], "score": 0.7 * r["score"]}
        for r in text_results:
            cid = r["chunk_id"]
            if cid in merged:
                merged[cid]["score"] += 0.3 * r["score"]
            else:
                merged[cid] = {"content": r["content"], "score": 0.3 * r["score"]}

        results = sorted(merged.values(), key=lambda x: x["score"], reverse=True)[: body.top_k]
    else:
        try:
            from src.loop.harvest.embedder import embed_texts
            query_embeddings = await embed_texts([body.query])
            results = await vector_search(db, body.inference_id, query_embeddings[0], top_k=body.top_k)
        except RuntimeError:
            results = await text_search(db, body.inference_id, body.query, top_k=body.top_k)

    return {"results": results, "total_chunks": total_chunks}


async def _harvest_all_background(
    inference_id: uuid.UUID,
    source_ids: list[tuple[uuid.UUID, str]],
) -> None:
    from src.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        for source_id, url in source_ids:
            await harvest_source(db, source_id, url, inference_id)
