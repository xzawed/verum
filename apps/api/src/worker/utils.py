"""Shared worker utilities."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession


async def safe_rollback(db: AsyncSession) -> None:
    """Rollback the current transaction, swallowing rollback errors.

    Use this before writing error state in exception handlers to ensure
    the session is not in a failed transaction when the error write runs.
    """
    try:
        await db.rollback()
    except Exception:  # noqa: BLE001
        pass
