"""Shared pytest fixtures for Verum API test suite."""
from __future__ import annotations

import os
import uuid
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

# Ensure DATABASE_URL is set before any src imports that validate it at module load.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://verum:verum@localhost:5432/verum",
)


@pytest.fixture
def mock_db() -> AsyncMock:
    """Return a lightweight AsyncMock for AsyncSession.

    Use this in unit tests that patch individual DB calls. The session
    has a pre-wired commit/rollback/flush cycle that tracks call counts.

    Usage::
        async def test_something(mock_db):
            mock_db.execute.return_value = make_result(...)
            await my_function(mock_db)
            mock_db.commit.assert_awaited_once()
    """
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    return session


def make_execute_result(rows: list[Any]) -> MagicMock:
    """Build a mock that mimics SQLAlchemy CursorResult for simple row lists.

    Args:
        rows: List of row tuples or MagicMock objects.

    Returns:
        A MagicMock that responds to .fetchall(), .fetchone(), .scalars(),
        .scalar_one_or_none(), .scalar_one(), and .mappings().first().
    """
    result = MagicMock()
    result.fetchall.return_value = rows
    result.fetchone.return_value = rows[0] if rows else None
    scalars = MagicMock()
    scalars.all.return_value = rows
    scalars.first.return_value = rows[0] if rows else None
    result.scalars.return_value = scalars
    result.scalar_one_or_none.return_value = rows[0] if rows else None
    result.scalar_one.return_value = rows[0] if rows else (_ for _ in ()).throw(
        Exception("No row found")
    )
    mappings_result = MagicMock()
    mappings_result.first.return_value = dict(rows[0]) if rows and hasattr(rows[0], "__iter__") else rows[0] if rows else None
    result.mappings.return_value = mappings_result
    return result


@pytest.fixture
def owner_user_id() -> uuid.UUID:
    """A stable owner UUID for use across related test cases."""
    return uuid.UUID("00000000-0000-0000-0000-000000000001")


# ---------------------------------------------------------------------------
# Real database integration fixture (requires DATABASE_URL + running Postgres)
# ---------------------------------------------------------------------------

def _is_db_available() -> bool:
    """Return True if DATABASE_URL points to a reachable Postgres instance."""
    import socket
    url = os.environ.get("DATABASE_URL", "")
    if "localhost" in url or "127.0.0.1" in url:
        try:
            sock = socket.create_connection(("localhost", 5432), timeout=1)
            sock.close()
            return True
        except OSError:
            return False
    return bool(url)


requires_db = pytest.mark.skipif(
    not _is_db_available(),
    reason="Postgres not reachable; set DATABASE_URL to run integration tests",
)


@pytest.fixture
async def async_db_session() -> AsyncGenerator[Any, None]:
    """Provide a real AsyncSession that rolls back after each test.

    Skipped automatically if Postgres is not reachable.

    Usage::
        @requires_db
        async def test_real_db_query(async_db_session):
            result = await repo.count_chunks(async_db_session, uuid.uuid4())
            assert result == 0
    """
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    db_url = os.environ["DATABASE_URL"]
    engine = create_async_engine(db_url, echo=False)
    async_session_factory = sessionmaker(  # type: ignore[call-overload]
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_factory() as session:
        async with session.begin():
            yield session
            await session.rollback()

    await engine.dispose()
