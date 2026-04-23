"""Shared DB helper for marking any loop stage row as error."""
from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def mark_error(
    db: AsyncSession,
    model: Any,
    row_id: uuid.UUID,
    message: str,
) -> None:
    """Set status='error' and error=message on any loop stage row.

    Args:
        db: Async SQLAlchemy session.
        model: SQLAlchemy ORM model class with id/status/error columns.
        row_id: Primary key of the row to update.
        message: Error message to store (truncated to 1024 chars).
    """
    row = (await db.execute(select(model).where(model.id == row_id))).scalar_one_or_none()
    if row is None:
        logger.warning("mark_error: %s %s not found, skipping", model.__tablename__, row_id)
        return
    row.status = "error"
    row.error = message[:1024]
    await db.commit()
