"""Tests for apps/api/src/db/session.py — get_db_for_user GUC round-trip."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from tests.conftest import requires_db


# ---------------------------------------------------------------------------
# Unit tests — get_db_for_user mock-based (no real DB needed)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_db_for_user_sets_config_and_yields():
    """get_db_for_user sets app.current_user_id and yields an AsyncSession."""
    from unittest.mock import AsyncMock, MagicMock, patch

    user_id = str(uuid.uuid4())
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    mock_factory = MagicMock(return_value=mock_session)

    with patch("src.db.session.AsyncSessionLocal", mock_factory):
        from src.db.session import get_db_for_user
        async with get_db_for_user(user_id) as db:
            assert db is mock_session

    # set_config must have been called (first execute call)
    first_call = mock_session.execute.await_args_list[0]
    sql_text = str(first_call[0][0])
    assert "set_config" in sql_text
    assert "app.current_user_id" in sql_text

    # RESET must be called in finally (last execute call)
    last_call = mock_session.execute.await_args_list[-1]
    reset_sql = str(last_call[0][0])
    assert "RESET" in reset_sql


@pytest.mark.asyncio
async def test_get_db_for_user_resets_guc_even_on_exception():
    """get_db_for_user must RESET app.current_user_id even when caller raises."""
    from unittest.mock import AsyncMock, MagicMock, patch

    user_id = str(uuid.uuid4())
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    mock_factory = MagicMock(return_value=mock_session)

    with patch("src.db.session.AsyncSessionLocal", mock_factory):
        from src.db.session import get_db_for_user
        with pytest.raises(ValueError, match="test exception"):
            async with get_db_for_user(user_id):
                raise ValueError("test exception")

    # RESET must still have been called
    called_sqls = [str(c[0][0]) for c in mock_session.execute.await_args_list]
    assert any("RESET" in s for s in called_sqls)


# ---------------------------------------------------------------------------
# Integration tests — require a real Postgres instance
# ---------------------------------------------------------------------------


@requires_db
@pytest.mark.asyncio
async def test_get_db_for_user_sets_and_clears_guc():
    """With a real DB: GUC is set inside context, cleared outside it.

    Uses an isolated engine (not the shared module-level one) to avoid
    corrupting the connection pool for subsequent tests that run under
    a different asyncio event loop.
    """
    import os
    from contextlib import asynccontextmanager
    from collections.abc import AsyncGenerator
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    db_url = os.environ["DATABASE_URL"]
    _engine = create_async_engine(db_url, echo=False)
    _SessionLocal = async_sessionmaker(_engine, expire_on_commit=False)

    @asynccontextmanager
    async def _get_db_for_user(user_id: str) -> AsyncGenerator[AsyncSession, None]:
        async with _SessionLocal() as session:
            await session.execute(
                text("SELECT set_config('app.current_user_id', :uid, false)"),
                {"uid": str(user_id)},
            )
            try:
                yield session
            finally:
                import contextlib
                with contextlib.suppress(Exception):
                    await session.execute(text("RESET app.current_user_id"))

    user_id = str(uuid.uuid4())

    async with _get_db_for_user(user_id) as db:
        result = await db.execute(text("SELECT current_setting('app.current_user_id', true)"))
        inside_value = result.scalar()

    assert inside_value == user_id

    async with _SessionLocal() as db:
        result = await db.execute(text("SELECT current_setting('app.current_user_id', true)"))
        outside_value = result.scalar()

    assert outside_value != user_id

    await _engine.dispose()
