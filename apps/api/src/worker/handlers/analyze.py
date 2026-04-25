"""ANALYZE job handler.

Payload schema:
  repo_url: str
  branch: str  (default "main")
  repo_id: str (UUID)
  analysis_id: str (UUID)
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

import os as _os

from src.loop.analyze.cloner import _BRANCH_RE, _GITHUB_URL_RE
from src.loop.analyze.pipeline import run_analysis
from src.loop.analyze.repository import mark_analysis_error, save_analysis_result
from src.worker.chain import enqueue_next
from src.worker.utils import safe_rollback


async def handle_analyze(
    db: AsyncSession,
    owner_user_id: uuid.UUID,
    payload: dict[str, Any],
) -> dict[str, Any]:
    repo_url: str = payload["repo_url"]
    branch: str = payload.get("branch", "main")
    repo_id = uuid.UUID(payload["repo_id"])
    analysis_id = uuid.UUID(payload["analysis_id"])

    # Defence-in-depth: re-validate inputs even though the API layer and Pydantic
    # already checked them.  A job inserted directly into verum_jobs bypasses those
    # layers; catching it here prevents a malicious URL from ever reaching the
    # git subprocess.
    if not _GITHUB_URL_RE.match(repo_url) and _os.environ.get("VERUM_TEST_MODE") != "1":
        raise ValueError(f"Rejected non-GitHub URL in job payload: {repo_url!r}")
    if not _BRANCH_RE.match(branch):
        raise ValueError(f"Rejected unsafe branch name in job payload: {branch!r}")

    try:
        result = await run_analysis(repo_url, branch=branch, repo_id=repo_id)
        await save_analysis_result(db, analysis_id, result)

        inference_id = uuid.uuid4()
        await db.execute(
            text(
                "INSERT INTO inferences (id, repo_id, analysis_id, status)"
                " VALUES (:id, :repo_id, :analysis_id, 'pending')"
            ),
            {
                "id": str(inference_id),
                "repo_id": str(repo_id),
                "analysis_id": str(analysis_id),
            },
        )

        await enqueue_next(
            db,
            kind="infer",
            payload={
                "analysis_id": str(analysis_id),
                "inference_id": str(inference_id),
            },
            owner_user_id=owner_user_id,
        )
        await db.commit()

        return {
            "analysis_id": str(analysis_id),
            "call_site_count": len(result.call_sites),
            "language_breakdown": result.language_breakdown,
            "inference_id": str(inference_id),
        }
    except Exception as exc:
        await safe_rollback(db)
        await mark_analysis_error(db, analysis_id, str(exc))
        raise
