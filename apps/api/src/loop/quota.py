"""Usage quota enforcement for Verum freemium tier."""
from __future__ import annotations

import logging
from datetime import date
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import FREE_PLAN

logger = logging.getLogger(__name__)

# Re-export as dict for callers that reference FREE_LIMITS directly
FREE_LIMITS = {
    "traces": FREE_PLAN.traces,
    "chunks": FREE_PLAN.chunks,
    "repos": FREE_PLAN.repos,
}


class QuotaExceededError(Exception):
    """Raised when a user exceeds their free tier quota."""

    def __init__(self, resource: str, used: int, limit: int) -> None:
        self.resource = resource
        self.used = used
        self.limit = limit
        super().__init__(f"Quota exceeded: {resource} ({used}/{limit})")


async def get_or_create_quota(
    session: AsyncSession, user_id: UUID, *, period: date | None = None
) -> dict:
    if period is None:
        today = date.today()
        period = date(today.year, today.month, 1)

    row = await session.execute(
        text("""
            INSERT INTO usage_quotas (user_id, period_start)
            VALUES (:user_id, :period)
            ON CONFLICT (user_id, period_start) DO UPDATE
                SET updated_at = now()
            RETURNING traces_used, chunks_stored, repos_connected, plan
        """),
        {"user_id": str(user_id), "period": period},
    )
    await session.commit()
    result = row.mappings().first()
    if result is None:
        logger.warning("get_or_create_quota: INSERT returned no row for user %s", user_id)
        return {"traces_used": 0, "chunks_stored": 0, "repos_connected": 0, "plan": "free"}
    return dict(result)


async def check_quota(
    session: AsyncSession, user_id: UUID, *, traces: int = 0, chunks: int = 0
) -> None:
    """Raise QuotaExceededError if adding these resources would exceed the free limit."""
    quota = await get_or_create_quota(session, user_id)
    if quota["plan"] != "free":
        return  # paid plans: no limit enforcement here
    if traces > 0 and quota["traces_used"] + traces > FREE_PLAN.traces:
        raise QuotaExceededError("traces", quota["traces_used"], FREE_PLAN.traces)
    if chunks > 0 and quota["chunks_stored"] + chunks > FREE_PLAN.chunks:
        raise QuotaExceededError("chunks", quota["chunks_stored"], FREE_PLAN.chunks)


async def increment_quota(
    session: AsyncSession, user_id: UUID, *, traces: int = 0, chunks: int = 0
) -> None:
    """Increment quota counters after successful resource creation."""
    today = date.today()
    period = date(today.year, today.month, 1)
    await session.execute(
        text("""
            INSERT INTO usage_quotas (user_id, period_start, traces_used, chunks_stored)
            VALUES (:user_id, :period, :traces, :chunks)
            ON CONFLICT (user_id, period_start) DO UPDATE
                SET traces_used = usage_quotas.traces_used + :traces,
                    chunks_stored = usage_quotas.chunks_stored + :chunks,
                    updated_at = now()
        """),
        {"user_id": str(user_id), "period": period, "traces": traces, "chunks": chunks},
    )
