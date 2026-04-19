"""FastAPI router for the INFER stage (F-2.1).

Endpoints:
  POST /v1/infer/{analysis_id}   — start inference job
  GET  /v1/infer/{inference_id}  — get inference result + suggested sources
  GET  /v1/analyses/{id}/inferences — list inferences for an analysis
"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.loop.analyze.repository import get_analysis
from .engine import run_infer
from .repository import (
    approve_source,
    create_pending_inference,
    get_harvest_sources,
    get_inference,
    list_analysis_inferences,
    mark_inference_error,
    reject_source,
    save_inference_result,
)

router = APIRouter(prefix="/v1", tags=["infer"])


class InferStartResponse(BaseModel):
    inference_id: uuid.UUID
    status: str = "pending"


class SourceResponse(BaseModel):
    source_id: uuid.UUID
    url: str
    title: str | None
    description: str | None
    status: str


@router.post("/infer/{analysis_id}", status_code=202, response_model=InferStartResponse)
async def start_infer(
    analysis_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InferStartResponse:
    analysis = await get_analysis(db, analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if analysis.status != "done":
        raise HTTPException(status_code=409, detail=f"Analysis is not done (status={analysis.status})")

    inference = await create_pending_inference(db, analysis.repo_id, analysis_id)
    background_tasks.add_task(
        _run_infer_background,
        analysis_id=analysis_id,
        inference_id=inference.id,
    )
    return InferStartResponse(inference_id=inference.id)


class InferenceResponse(BaseModel):
    status: str
    inference_id: uuid.UUID
    analysis_id: uuid.UUID | None = None
    repo_id: uuid.UUID | None = None
    domain: str | None = None
    tone: str | None = None
    language: str | None = None
    user_type: str | None = None
    confidence: float | None = None
    summary: str | None = None
    error: str | None = None
    suggested_sources: list[SourceResponse] | None = None


class InferenceSummary(BaseModel):
    inference_id: uuid.UUID
    status: str
    domain: str | None
    confidence: float | None
    created_at: str | None


@router.get("/infer/{inference_id}", response_model=InferenceResponse)
async def get_infer_result(
    inference_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InferenceResponse:
    row = await get_inference(db, inference_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Inference not found")

    if row.status in ("pending", "running"):
        return InferenceResponse(status=row.status, inference_id=row.id)

    if row.status == "error":
        return InferenceResponse(status="error", inference_id=row.id, error=row.error)

    sources = await get_harvest_sources(db, inference_id)
    return InferenceResponse(
        status="done",
        inference_id=row.id,
        analysis_id=row.analysis_id,
        repo_id=row.repo_id,
        domain=row.domain,
        tone=row.tone,
        language=row.language,
        user_type=row.user_type,
        confidence=row.confidence,
        summary=row.summary,
        suggested_sources=[
            SourceResponse(
                source_id=s.id,
                url=s.url,
                title=s.title,
                description=s.description,
                status=s.status,
            )
            for s in sources
        ],
    )


@router.get("/analyses/{analysis_id}/inferences", response_model=list[InferenceSummary])
async def list_inferences(
    analysis_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[InferenceSummary]:
    rows = await list_analysis_inferences(db, analysis_id)
    return [
        InferenceSummary(
            inference_id=r.id,
            status=r.status,
            domain=r.domain,
            confidence=r.confidence,
            created_at=r.created_at.isoformat() if r.created_at else None,
        )
        for r in rows
    ]


@router.post("/sources/{source_id}/approve", response_model=SourceResponse)
async def approve_harvest_source(
    source_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SourceResponse:
    try:
        row = await approve_source(db, source_id)
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Source not found")
    return SourceResponse(
        source_id=row.id,
        url=row.url,
        title=row.title,
        description=row.description,
        status=row.status,
    )


@router.post("/sources/{source_id}/reject", response_model=SourceResponse)
async def reject_harvest_source(
    source_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SourceResponse:
    try:
        row = await reject_source(db, source_id)
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Source not found")
    return SourceResponse(
        source_id=row.id,
        url=row.url,
        title=row.title,
        description=row.description,
        status=row.status,
    )


async def _run_infer_background(
    analysis_id: uuid.UUID,
    inference_id: uuid.UUID,
) -> None:
    from src.db.session import AsyncSessionLocal
    from src.loop.analyze.models import AnalysisResult, LLMCallSite, ModelConfig, PromptTemplate
    from datetime import datetime, timezone

    async with AsyncSessionLocal() as db:
        try:
            analysis = await get_analysis(db, analysis_id)
            if analysis is None:
                await mark_inference_error(db, inference_id, "analysis not found")
                return

            # Reconstruct AnalysisResult from stored JSONB
            result = AnalysisResult(
                repo_id=analysis.repo_id,
                call_sites=[LLMCallSite(**cs) for cs in (analysis.call_sites or [])],
                prompt_templates=[PromptTemplate(**pt) for pt in (analysis.prompt_templates or [])],
                model_configs=[ModelConfig(**mc) for mc in (analysis.model_configs or [])],
                language_breakdown=analysis.language_breakdown or {},
                analyzed_at=analysis.analyzed_at or datetime.now(tz=timezone.utc),
            )

            inferred = await run_infer(result)
            # Patch analysis_id (engine sets it to repo_id as placeholder)
            inferred = inferred.model_copy(update={"analysis_id": analysis_id})

            await save_inference_result(
                db,
                inference_id,
                inferred,
                raw=inferred.model_dump(mode="json"),
            )
        except Exception as exc:
            await mark_inference_error(db, inference_id, str(exc)[:1024])
