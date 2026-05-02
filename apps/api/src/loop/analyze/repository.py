"""Database I/O for the ANALYZE stage."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.enums import AnalysisStatus
from src.db.models.analyses import Analysis
from src.db.models.repos import Repo

from .models import AnalysisResult


async def get_or_create_repo(
    db: AsyncSession,
    github_url: str,
    branch: str = "main",
    *,
    owner_user_id: uuid.UUID,
) -> Repo:
    result = await db.execute(
        select(Repo).where(
            Repo.owner_user_id == owner_user_id,
            Repo.github_url == github_url,
        )
    )
    repo = result.scalar_one_or_none()
    if repo is None:
        repo = Repo(
            id=uuid.uuid4(),
            github_url=github_url,
            default_branch=branch,
            owner_user_id=owner_user_id,
        )
        db.add(repo)
        await db.flush()
    return repo


async def create_pending_analysis(
    db: AsyncSession,
    repo_id: uuid.UUID,
) -> Analysis:
    analysis = Analysis(
        id=uuid.uuid4(),
        repo_id=repo_id,
        status=AnalysisStatus.PENDING,
        started_at=datetime.now(tz=timezone.utc),
    )
    db.add(analysis)
    await db.flush()
    await db.commit()
    return analysis


async def save_analysis_result(
    db: AsyncSession,
    analysis_id: uuid.UUID,
    result: AnalysisResult,
) -> None:
    stmt = select(Analysis).where(Analysis.id == analysis_id)
    row = (await db.execute(stmt)).scalar_one()
    row.status = AnalysisStatus.DONE
    row.call_sites = [cs.model_dump() for cs in result.call_sites]
    row.prompt_templates = [pt.model_dump() for pt in result.prompt_templates]
    row.model_configs = [mc.model_dump() for mc in result.model_configs]
    row.language_breakdown = result.language_breakdown  # type: ignore[assignment]
    row.analyzed_at = result.analyzed_at
    # Also update the repo's last_analyzed_at
    repo_stmt = select(Repo).where(Repo.id == result.repo_id)
    repo = (await db.execute(repo_stmt)).scalar_one_or_none()
    if repo:
        repo.last_analyzed_at = result.analyzed_at


async def mark_analysis_error(
    db: AsyncSession,
    analysis_id: uuid.UUID,
    error: str,
) -> None:
    from src.db.error_helpers import mark_error
    await mark_error(db, Analysis, analysis_id, error)


async def get_analysis(
    db: AsyncSession,
    analysis_id: uuid.UUID,
) -> Analysis | None:
    stmt = select(Analysis).where(Analysis.id == analysis_id)
    return (await db.execute(stmt)).scalar_one_or_none()


async def list_repo_analyses(
    db: AsyncSession,
    repo_id: uuid.UUID,
) -> list[Analysis]:
    stmt = select(Analysis).where(Analysis.repo_id == repo_id).order_by(Analysis.started_at.desc())
    return list((await db.execute(stmt)).scalars().all())
