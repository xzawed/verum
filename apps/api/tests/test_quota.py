"""Tests for usage quota module."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from src.loop.quota import (
    QuotaExceededError,
    FREE_LIMITS,
    check_quota,
    get_or_create_quota,
    increment_quota,
)


def make_session(quota_row: dict):
    """Return a mock AsyncSession whose execute returns the given quota dict."""
    result = MagicMock()
    result.mappings.return_value.first.return_value = quota_row
    session = AsyncMock()
    session.execute.return_value = result
    return session


@pytest.mark.asyncio
async def test_check_quota_free_under_limit():
    session = make_session({"traces_used": 500, "chunks_stored": 0, "repos_connected": 0, "plan": "free"})
    # Should not raise
    await check_quota(session, uuid4(), traces=100)


@pytest.mark.asyncio
async def test_check_quota_free_over_trace_limit():
    session = make_session({"traces_used": 950, "chunks_stored": 0, "repos_connected": 0, "plan": "free"})
    with pytest.raises(QuotaExceededError) as exc_info:
        await check_quota(session, uuid4(), traces=100)
    assert exc_info.value.resource == "traces"
    assert exc_info.value.limit == FREE_LIMITS["traces"]


@pytest.mark.asyncio
async def test_check_quota_paid_skips_limit():
    session = make_session({"traces_used": 99999, "chunks_stored": 0, "repos_connected": 0, "plan": "pro"})
    # Should not raise even over limit
    await check_quota(session, uuid4(), traces=1000)


@pytest.mark.asyncio
async def test_check_quota_chunks_over_limit():
    session = make_session({"traces_used": 0, "chunks_stored": 9900, "repos_connected": 0, "plan": "free"})
    with pytest.raises(QuotaExceededError) as exc_info:
        await check_quota(session, uuid4(), chunks=200)
    assert exc_info.value.resource == "chunks"


@pytest.mark.asyncio
async def test_get_or_create_quota_returns_default_when_no_row():
    """If the INSERT returns no row, a safe default dict is returned (covers lines 54-55)."""
    result_mock = MagicMock()
    result_mock.mappings.return_value.first.return_value = None
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result_mock)

    quota = await get_or_create_quota(session, uuid4())

    assert quota["plan"] == "free"
    assert quota["chunks_stored"] == 0
    assert quota["traces_used"] == 0


@pytest.mark.asyncio
async def test_increment_quota_executes_upsert():
    """increment_quota calls session.execute with the upsert SQL (covers lines 76-78)."""
    session = AsyncMock()
    await increment_quota(session, uuid4(), traces=5, chunks=10)
    session.execute.assert_awaited_once()
