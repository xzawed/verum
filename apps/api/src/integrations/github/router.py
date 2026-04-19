"""FastAPI router for user/repo management (Phase 2.5 multi-tenant foundation).

Endpoints (all require Bearer JWT):
  GET    /v1/me                          — current user profile
  GET    /v1/me/repos                    — list user's registered repos
  POST   /v1/me/repos                    — register a new repo
  GET    /v1/me/repos/{repo_id}          — repo detail
  DELETE /v1/me/repos/{repo_id}          — delete repo + cascade
  GET    /v1/me/repos/{repo_id}/status   — per-repo Loop progress dashboard
"""
from __future__ import annotations

import re
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.db.models.analyses import Analysis
from src.db.models.harvest_sources import HarvestSource
from src.db.models.inferences import Inference
from src.db.models.repos import Repo
from src.db.models.users import User
from src.db.session import get_db

router = APIRouter(prefix="/v1/me", tags=["me"])

_GITHUB_URL_RE = re.compile(
    r"^https://github\.com/[\w.\-]+/[\w.\-]+(\.git)?$"
)


# ── Pydantic shapes ────────────────────────────────────────────────────────────

class UserProfile(BaseModel):
    user_id: uuid.UUID
    github_id: int
    github_login: str
    email: str | None
    avatar_url: str | None


class RegisterRepoRequest(BaseModel):
    repo_url: str
    default_branch: str = "main"


class RepoDetail(BaseModel):
    repo_id: uuid.UUID
    github_url: str
    default_branch: str
    last_analyzed_at: str | None
    created_at: str


class LatestAnalysis(BaseModel):
    analysis_id: uuid.UUID
    status: str
    call_sites_count: int | None
    analyzed_at: str | None


class LatestInference(BaseModel):
    inference_id: uuid.UUID
    status: str
    domain: str | None
    confidence: float | None
    approved_sources: int
    total_sources: int


class LatestHarvest(BaseModel):
    inference_id: uuid.UUID
    sources_done: int
    sources_total: int
    total_chunks: int


class RepoStatus(BaseModel):
    repo: RepoDetail
    latest_analysis: LatestAnalysis | None
    latest_inference: LatestInference | None
    latest_harvest: LatestHarvest | None


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("", response_model=UserProfile)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserProfile:
    return UserProfile(
        user_id=current_user.id,
        github_id=current_user.github_id,
        github_login=current_user.github_login,
        email=current_user.email,
        avatar_url=current_user.avatar_url,
    )


@router.get("/repos", response_model=list[RepoDetail])
async def list_repos(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[RepoDetail]:
    rows = (
        await db.execute(
            select(Repo)
            .where(Repo.owner_user_id == current_user.id)
            .order_by(Repo.created_at.desc())
        )
    ).scalars().all()
    return [_repo_to_detail(r) for r in rows]


@router.post("/repos", status_code=201, response_model=RepoDetail)
async def register_repo(
    body: RegisterRepoRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RepoDetail:
    url = body.repo_url.rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]
    if not _GITHUB_URL_RE.match(url):
        raise HTTPException(
            status_code=422,
            detail="repo_url must be a valid https://github.com/<owner>/<repo> URL",
        )

    existing = (
        await db.execute(
            select(Repo).where(
                Repo.owner_user_id == current_user.id,
                Repo.github_url == url,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Repo already registered")

    repo = Repo(
        id=uuid.uuid4(),
        github_url=url,
        owner_user_id=current_user.id,
        default_branch=body.default_branch,
    )
    db.add(repo)
    await db.commit()
    await db.refresh(repo)
    return _repo_to_detail(repo)


@router.get("/repos/{repo_id}", response_model=RepoDetail)
async def get_repo(
    repo_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RepoDetail:
    repo = await _require_owned_repo(db, repo_id, current_user.id)
    return _repo_to_detail(repo)


@router.delete("/repos/{repo_id}", status_code=204)
async def delete_repo(
    repo_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    repo = await _require_owned_repo(db, repo_id, current_user.id)
    await db.delete(repo)
    await db.commit()


@router.get("/repos/{repo_id}/status", response_model=RepoStatus)
async def get_repo_status(
    repo_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RepoStatus:
    repo = await _require_owned_repo(db, repo_id, current_user.id)

    # Latest analysis
    latest_analysis_row = (
        await db.execute(
            select(Analysis)
            .where(Analysis.repo_id == repo_id)
            .order_by(Analysis.started_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    latest_analysis: LatestAnalysis | None = None
    latest_inference: LatestInference | None = None
    latest_harvest: LatestHarvest | None = None

    if latest_analysis_row:
        latest_analysis = LatestAnalysis(
            analysis_id=latest_analysis_row.id,
            status=latest_analysis_row.status,
            call_sites_count=len(latest_analysis_row.call_sites) if latest_analysis_row.call_sites else None,
            analyzed_at=latest_analysis_row.analyzed_at.isoformat() if latest_analysis_row.analyzed_at else None,
        )

        # Latest inference for this analysis
        latest_inference_row = (
            await db.execute(
                select(Inference)
                .where(Inference.analysis_id == latest_analysis_row.id)
                .order_by(Inference.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

        if latest_inference_row:
            sources = (
                await db.execute(
                    select(HarvestSource).where(
                        HarvestSource.inference_id == latest_inference_row.id
                    )
                )
            ).scalars().all()
            approved = sum(1 for s in sources if s.status == "approved")
            latest_inference = LatestInference(
                inference_id=latest_inference_row.id,
                status=latest_inference_row.status,
                domain=latest_inference_row.domain,
                confidence=latest_inference_row.confidence,
                approved_sources=approved,
                total_sources=len(sources),
            )

            # Harvest stats
            done_sources = [s for s in sources if s.status == "done"]
            if done_sources or any(s.status in ("crawling", "error") for s in sources):
                total_chunks_row = await db.execute(
                    text("SELECT COUNT(*) FROM chunks WHERE inference_id = :iid"),
                    {"iid": str(latest_inference_row.id)},
                )
                chunk_count = int((total_chunks_row.fetchone() or (0,))[0])
                latest_harvest = LatestHarvest(
                    inference_id=latest_inference_row.id,
                    sources_done=len(done_sources),
                    sources_total=len(sources),
                    total_chunks=chunk_count,
                )

    return RepoStatus(
        repo=_repo_to_detail(repo),
        latest_analysis=latest_analysis,
        latest_inference=latest_inference,
        latest_harvest=latest_harvest,
    )


# ── Helpers ────────────────────────────────────────────────────────────────────

def _repo_to_detail(repo: Repo) -> RepoDetail:
    return RepoDetail(
        repo_id=repo.id,
        github_url=repo.github_url,
        default_branch=repo.default_branch,
        last_analyzed_at=repo.last_analyzed_at.isoformat() if repo.last_analyzed_at else None,
        created_at=repo.created_at.isoformat(),
    )


async def _require_owned_repo(
    db: AsyncSession, repo_id: uuid.UUID, user_id: uuid.UUID
) -> Repo:
    repo = (
        await db.execute(select(Repo).where(Repo.id == repo_id))
    ).scalar_one_or_none()
    if repo is None or repo.owner_user_id != user_id:
        raise HTTPException(status_code=404, detail="Repo not found")
    return repo
