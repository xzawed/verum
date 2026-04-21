"""Job chaining: enqueue the next stage after a completed job."""
from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def enqueue_next(
    db: AsyncSession,
    *,
    kind: str,
    payload: dict[str, Any],
    owner_user_id: uuid.UUID,
) -> None:
    """Insert a new queued job — the DB AFTER INSERT trigger fires pg_notify immediately."""
    await db.execute(
        text(
            "INSERT INTO verum_jobs (kind, payload, owner_user_id, status)"
            " VALUES (:k, :p, :u, 'queued')"
        ),
        {"k": kind, "p": json.dumps(payload, default=str), "u": str(owner_user_id)},
    )
    # Caller owns commit — do not commit here
