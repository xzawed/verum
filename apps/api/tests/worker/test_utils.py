"""Tests for src.worker.utils."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.worker.utils import safe_rollback


@pytest.mark.asyncio
async def test_safe_rollback_calls_rollback(mock_db: AsyncMock) -> None:
    """safe_rollback invokes db.rollback()."""
    await safe_rollback(mock_db)
    mock_db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_safe_rollback_swallows_rollback_exception() -> None:
    """safe_rollback silently ignores any exception raised by db.rollback()."""
    db = AsyncMock()
    db.rollback = AsyncMock(side_effect=Exception("connection lost"))
    # Should not propagate the exception
    await safe_rollback(db)
