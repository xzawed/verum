"""Unit tests for src.worker.runner core functions.

Tests cover:
- _mark_failed retry vs final-fail logic (no external I/O)
- _claim_one SQL execution and row mapping
- _dispatch_job handler success → mark_done, handler exception → mark_failed
- SKIP LOCKED: two concurrent _claim_one calls — only one gets the job
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from src.worker.runner import (
    MAX_ATTEMPTS,
    _claim_one,
    _dispatch_job,
    _mark_done,
    _mark_failed,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_mapping_result(row: dict | None) -> MagicMock:
    """Build a SQLAlchemy CursorResult mock whose .mappings().first() returns row."""
    result = MagicMock()
    mappings = MagicMock()
    mappings.first.return_value = row
    result.mappings.return_value = mappings
    return result


# ── _mark_failed ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mark_failed_below_max_attempts_requeues(mock_db: AsyncMock) -> None:
    """A failed job with attempts < MAX_ATTEMPTS is put back to 'queued'."""
    job_id = uuid.uuid4()
    await _mark_failed(mock_db, job_id, "something broke", attempts=1)

    mock_db.execute.assert_awaited_once()
    params = mock_db.execute.await_args.args[1]
    assert params["status"] == "queued"
    assert params["error"] == "something broke"
    assert params["id"] == job_id
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_mark_failed_at_max_attempts_sets_failed(mock_db: AsyncMock) -> None:
    """A failed job that has exhausted retries is set to 'failed'."""
    job_id = uuid.uuid4()
    await _mark_failed(mock_db, job_id, "permanent error", attempts=MAX_ATTEMPTS)

    params = mock_db.execute.await_args.args[1]
    assert params["status"] == "failed"


@pytest.mark.asyncio
async def test_mark_failed_above_max_attempts_also_sets_failed(mock_db: AsyncMock) -> None:
    """Attempts exceeding MAX_ATTEMPTS (edge-case) still results in 'failed'."""
    job_id = uuid.uuid4()
    await _mark_failed(mock_db, job_id, "error", attempts=MAX_ATTEMPTS + 5)

    params = mock_db.execute.await_args.args[1]
    assert params["status"] == "failed"


@pytest.mark.asyncio
async def test_mark_failed_attempt_one_below_max_is_queued(mock_db: AsyncMock) -> None:
    """MAX_ATTEMPTS - 1 attempts → still retryable → 'queued'."""
    job_id = uuid.uuid4()
    await _mark_failed(mock_db, job_id, "transient", attempts=MAX_ATTEMPTS - 1)

    params = mock_db.execute.await_args.args[1]
    assert params["status"] == "queued"


# ── _mark_done ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mark_done_commits(mock_db: AsyncMock) -> None:
    """_mark_done stores a JSON result and commits."""
    job_id = uuid.uuid4()
    await _mark_done(mock_db, job_id, {"chunks": 42})

    mock_db.execute.assert_awaited_once()
    params = mock_db.execute.await_args.args[1]
    assert params["id"] == job_id
    assert '"chunks"' in params["result"]
    mock_db.commit.assert_awaited_once()


# ── _claim_one ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_claim_one_returns_job_when_row_found(mock_db: AsyncMock) -> None:
    """When a queued row exists, _claim_one returns it as a plain dict."""
    job_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    row = {
        "id": job_id,
        "kind": "analyze",
        "payload": {"repo_id": str(uuid.uuid4()), "repo_url": "https://github.com/test/repo"},
        "owner_user_id": owner_id,
        "attempts": 1,
    }
    mock_db.execute.return_value = _make_mapping_result(row)

    result = await _claim_one(mock_db)

    assert result == row
    mock_db.commit.assert_awaited_once()
    # Verify the UPDATE uses SKIP LOCKED (present in the SQL string)
    sql_text = str(mock_db.execute.await_args.args[0])
    assert "SKIP LOCKED" in sql_text


@pytest.mark.asyncio
async def test_claim_one_returns_none_when_queue_empty(mock_db: AsyncMock) -> None:
    """When no queued job exists, _claim_one returns None."""
    mock_db.execute.return_value = _make_mapping_result(None)

    result = await _claim_one(mock_db)

    assert result is None
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_claim_one_skip_locked_prevents_double_claim(mock_db: AsyncMock) -> None:
    """Simulate two concurrent workers: only one gets the job.

    Both workers call _claim_one simultaneously.  SKIP LOCKED means the second
    UPDATE finds 0 rows (the first already locked them).  We model this by
    having the second mock call return None.
    """
    job_id = uuid.uuid4()
    row = {
        "id": job_id,
        "kind": "analyze",
        "payload": {},
        "owner_user_id": uuid.uuid4(),
        "attempts": 1,
    }
    # Worker 1 claims the job; worker 2 sees nothing (SKIP LOCKED)
    worker1_db = AsyncMock()
    worker1_db.execute.return_value = _make_mapping_result(row)
    worker1_db.commit = AsyncMock()

    worker2_db = AsyncMock()
    worker2_db.execute.return_value = _make_mapping_result(None)
    worker2_db.commit = AsyncMock()

    result1 = await _claim_one(worker1_db)
    result2 = await _claim_one(worker2_db)

    assert result1 == row
    assert result2 is None


# ── _dispatch_job ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_dispatch_job_success_calls_mark_done() -> None:
    """When a handler completes successfully, _mark_done is called."""
    job_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    job = {
        "id": job_id,
        "kind": "analyze",
        "payload": {"repo_id": str(uuid.uuid4()), "repo_url": "https://github.com/test/r"},
        "owner_user_id": owner_id,
        "attempts": 1,
    }

    mock_handler = AsyncMock(return_value={"ok": True})
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("src.worker.runner._HANDLERS", {"analyze": mock_handler}),
        patch("src.worker.runner._PAYLOAD_SCHEMAS", {}),
        patch("src.worker.runner.AsyncSessionLocal", return_value=mock_session),
        patch("src.worker.runner._mark_done", new=AsyncMock()) as mock_done,
        patch("src.worker.runner._mark_failed", new=AsyncMock()) as mock_failed,
    ):
        await _dispatch_job(job)

    mock_handler.assert_awaited_once()
    mock_done.assert_awaited_once()
    mock_failed.assert_not_awaited()


@pytest.mark.asyncio
async def test_dispatch_job_handler_exception_calls_mark_failed() -> None:
    """When a handler raises, _mark_failed is called; _mark_done is not."""
    job_id = uuid.uuid4()
    job = {
        "id": job_id,
        "kind": "infer",
        "payload": {"analysis_id": str(uuid.uuid4())},
        "owner_user_id": uuid.uuid4(),
        "attempts": 1,
    }

    mock_handler = AsyncMock(side_effect=RuntimeError("LLM timeout"))
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("src.worker.runner._HANDLERS", {"infer": mock_handler}),
        patch("src.worker.runner._PAYLOAD_SCHEMAS", {}),
        patch("src.worker.runner.AsyncSessionLocal", return_value=mock_session),
        patch("src.worker.runner._mark_done", new=AsyncMock()) as mock_done,
        patch("src.worker.runner._mark_failed", new=AsyncMock()) as mock_failed,
    ):
        await _dispatch_job(job)

    mock_done.assert_not_awaited()
    mock_failed.assert_awaited_once()
    _, called_job_id, error_msg, _ = mock_failed.await_args.args
    assert called_job_id == job_id
    assert "LLM timeout" in error_msg


@pytest.mark.asyncio
async def test_dispatch_job_unknown_kind_calls_mark_failed() -> None:
    """A job with an unknown kind is immediately failed without calling any handler."""
    job = {
        "id": uuid.uuid4(),
        "kind": "unknown_kind",
        "payload": {},
        "owner_user_id": uuid.uuid4(),
        "attempts": 1,
    }

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("src.worker.runner.AsyncSessionLocal", return_value=mock_session),
        patch("src.worker.runner._mark_failed", new=AsyncMock()) as mock_failed,
    ):
        await _dispatch_job(job)

    mock_failed.assert_awaited_once()
    error_msg = mock_failed.await_args.args[2]
    assert "unknown job kind" in error_msg
