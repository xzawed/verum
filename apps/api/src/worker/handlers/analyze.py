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

from sqlalchemy.ext.asyncio import AsyncSession

from src.loop.analyze.cloner import RepoCloneError
from src.loop.analyze.pipeline import run_analysis
from src.loop.analyze.repository import mark_analysis_error, save_analysis_result


async def handle_analyze(
    db: AsyncSession,
    owner_user_id: uuid.UUID,
    payload: dict[str, Any],
) -> dict[str, Any]:
    repo_url: str = payload["repo_url"]
    branch: str = payload.get("branch", "main")
    repo_id = uuid.UUID(payload["repo_id"])
    analysis_id = uuid.UUID(payload["analysis_id"])

    try:
        result = await run_analysis(repo_url, branch=branch, repo_id=repo_id)
        await save_analysis_result(db, analysis_id, result)
        return {
            "analysis_id": str(analysis_id),
            "call_site_count": len(result.call_sites),
            "language_breakdown": result.language_breakdown,
        }
    except RepoCloneError as exc:
        await mark_analysis_error(db, analysis_id, str(exc))
        raise
    except Exception as exc:
        await mark_analysis_error(db, analysis_id, str(exc))
        raise
