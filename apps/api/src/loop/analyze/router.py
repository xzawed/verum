"""FastAPI router for the ANALYZE stage (F-1.8).

Endpoints:
  POST /v1/analyze         — start analysis job
  GET  /v1/analyze/{id}   — get analysis result
  GET  /v1/repos/{id}/analyses — list analyses for a repo
"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.db.models.repos import Repo
from src.db.models.users import User
from src.db.session import get_db
from .cloner import RepoCloneError
from .pipeline import run_analysis
from .repository import (
    create_pending_analysis,
    get_analysis,
    get_or_create_repo,
    list_repo_analyses,
    mark_analysis_error,
    save_analysis_result,
)

router = APIRouter(prefix="/v1", tags=["analyze"])


class AnalyzeRequest(BaseModel):
    repo_url: str
    branch: str = "main"


class AnalyzeStartResponse(BaseModel):
    analysis_id: uuid.UUID
    status: str = "pending"


class AnalysisSummary(BaseModel):
    analysis_id: uuid.UUID
    status: str
    call_site_count: int | None
    analyzed_at: str | None


@router.post("/analyze", status_code=202, response_model=AnalyzeStartResponse)
async def start_analyze(
    body: AnalyzeRequest,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AnalyzeStartResponse:
    repo = await get_or_create_repo(
        db, body.repo_url, body.branch, owner_user_id=current_user.id
    )
    analysis = await create_pending_analysis(db, repo.id)

    background_tasks.add_task(
        _run_analysis_background,
        repo_url=body.repo_url,
        branch=body.branch,
        repo_id=repo.id,
        analysis_id=analysis.id,
    )
    return AnalyzeStartResponse(analysis_id=analysis.id)


class AnalysisResponse(BaseModel):
    status: str
    analysis_id: uuid.UUID
    started_at: str | None = None
    error: str | None = None
    repo_id: uuid.UUID | None = None
    call_sites: list[object] | None = None
    prompt_templates: list[object] | None = None
    model_configs: list[object] | None = None
    language_breakdown: dict[str, object] | None = None
    analyzed_at: str | None = None


@router.get("/analyze/{analysis_id}", response_model=AnalysisResponse)
async def get_analyze_result(
    analysis_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AnalysisResponse:
    row = await get_analysis(db, analysis_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Analysis not found")

    # Verify ownership via the repo
    repo = (await db.execute(select(Repo).where(Repo.id == row.repo_id))).scalar_one_or_none()
    if repo is None or repo.owner_user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Analysis not found")

    if row.status in ("pending", "running"):
        return AnalysisResponse(
            status=row.status,
            analysis_id=row.id,
            started_at=row.started_at.isoformat() if row.started_at else None,
        )
    if row.status == "error":
        return AnalysisResponse(status="error", analysis_id=row.id, error=row.error)
    return AnalysisResponse(
        status="done",
        analysis_id=row.id,
        repo_id=row.repo_id,
        call_sites=row.call_sites or [],
        prompt_templates=row.prompt_templates or [],
        model_configs=row.model_configs or [],
        language_breakdown=row.language_breakdown or {},
        analyzed_at=row.analyzed_at.isoformat() if row.analyzed_at else None,
    )


@router.get("/repos/{repo_id}/analyses", response_model=list[AnalysisSummary])
async def list_analyses(
    repo_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[AnalysisSummary]:
    repo = (await db.execute(select(Repo).where(Repo.id == repo_id))).scalar_one_or_none()
    if repo is None or repo.owner_user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Repo not found")

    rows = await list_repo_analyses(db, repo_id)
    return [
        AnalysisSummary(
            analysis_id=row.id,
            status=row.status,
            call_site_count=len(row.call_sites) if row.call_sites else None,
            analyzed_at=row.analyzed_at.isoformat() if row.analyzed_at else None,
        )
        for row in rows
    ]


async def _run_analysis_background(
    repo_url: str,
    branch: str,
    repo_id: uuid.UUID,
    analysis_id: uuid.UUID,
) -> None:
    from src.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        try:
            result = await run_analysis(repo_url, branch=branch, repo_id=repo_id)
            await save_analysis_result(db, analysis_id, result)
        except RepoCloneError as exc:
            await mark_analysis_error(db, analysis_id, f"clone:{exc.kind}:{exc}")
        except Exception as exc:
            await mark_analysis_error(db, analysis_id, str(exc)[:1024])
