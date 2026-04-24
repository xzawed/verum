"""Shared DB helpers used across all loop stages."""
from __future__ import annotations

from typing import Any

from sqlalchemy import TextClause
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession


async def execute_commit(
    db: AsyncSession,
    stmt: TextClause,
    params: dict[str, Any],
) -> CursorResult[Any]:
    """Execute a raw-SQL statement and immediately commit the transaction.

    For statements that need to inspect rows before committing, call
    db.execute() and db.commit() separately.  CursorResult rows are
    buffered before commit, so callers can chain .mappings().first() etc.
    on the returned result safely.

    Args:
        db: Active async SQLAlchemy session.
        stmt: A text() clause.
        params: Bind-parameter dict matched against :name placeholders.

    Returns:
        The CursorResult from db.execute() — rows buffered, safe to read
        after commit.
    """
    result = await db.execute(stmt, params)
    await db.commit()
    return result
