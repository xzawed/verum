"""Unit tests for src.worker.runner core functions.

Tests cover:
- _reset_stale requeue logic
- _mark_failed retry vs final-fail logic (no external I/O)
- _claim_one SQL execution and row mapping
- _mark_done JSON serialization
- _dispatch_job handler success → mark_done, handler exception → mark_failed
- _dispatch_job payload schema validation
- SKIP LOCKED: two concurrent _claim_one calls — only one gets the job
- _heartbeat_loop success and failure paths
- _stale_reset_loop iteration and exception swallowing
"""
from __future__ import annotations

import asyncio
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from src.worker.runner import (
    MAX_ATTEMPTS,
    _claim_one,
    _dispatch_job,
    _heartbeat_loop,
    _mark_done,
    _mark_failed,
    _reset_stale,
    _stale_reset_loop,
    _update_heartbeat,
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


# ── _reset_stale ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_reset_stale_executes_update_query(mock_db: AsyncMock) -> None:
    """_reset_stale issues a single UPDATE touching 'running' → 'queued' rows."""
    mock_db.execute.return_value = MagicMock(fetchall=MagicMock(return_value=[]))

    await _reset_stale(mock_db)

    mock_db.execute.assert_awaited_once()
    sql_text = str(mock_db.execute.await_args.args[0])
    # The UPDATE should reference both source status and target status
    assert "running" in sql_text
    assert "queued" in sql_text


@pytest.mark.asyncio
async def test_reset_stale_commits(mock_db: AsyncMock) -> None:
    """_reset_stale calls db.commit() once after the UPDATE."""
    mock_db.execute.return_value = MagicMock(fetchall=MagicMock(return_value=[]))

    await _reset_stale(mock_db)

    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_reset_stale_passes_cutoff_param(mock_db: AsyncMock) -> None:
    """_reset_stale passes a :cutoff bind parameter (datetime) to the UPDATE."""
    from datetime import datetime

    mock_db.execute.return_value = MagicMock(fetchall=MagicMock(return_value=[]))

    await _reset_stale(mock_db)

    params = mock_db.execute.await_args.args[1]
    assert "cutoff" in params
    assert isinstance(params["cutoff"], datetime)


# ── _mark_done JSON serialization ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mark_done_serializes_result_to_json_string(mock_db: AsyncMock) -> None:
    """_mark_done passes the result as a JSON string, not a raw dict."""
    job_id = uuid.uuid4()
    payload = {"status": "ok", "count": 7}

    await _mark_done(mock_db, job_id, payload)

    params = mock_db.execute.await_args.args[1]
    # result param must be a JSON string, not a dict
    assert isinstance(params["result"], str)
    parsed = json.loads(params["result"])
    assert parsed == payload


@pytest.mark.asyncio
async def test_mark_done_serializes_uuid_values(mock_db: AsyncMock) -> None:
    """_mark_done handles UUID values via default=str without raising."""
    job_id = uuid.uuid4()
    result_with_uuid = {"id": uuid.uuid4(), "label": "test"}

    # Should not raise a TypeError for non-serializable UUID
    await _mark_done(mock_db, job_id, result_with_uuid)

    params = mock_db.execute.await_args.args[1]
    parsed = json.loads(params["result"])
    assert "id" in parsed


# ── _dispatch_job payload schema validation ───────────────────────────────────


@pytest.mark.asyncio
async def test_dispatch_job_invalid_payload_calls_mark_failed_not_handler() -> None:
    """A job with a payload that fails Pydantic validation is failed immediately."""
    from src.worker.payloads import DeployPayload

    job_id = uuid.uuid4()
    job = {
        "id": job_id,
        "kind": "deploy",
        # Missing required 'generation_id' field → Pydantic validation error
        "payload": {"wrong_field": "oops"},
        "owner_user_id": uuid.uuid4(),
        "attempts": 1,
    }

    mock_handler = AsyncMock()
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("src.worker.runner._HANDLERS", {"deploy": mock_handler}),
        patch("src.worker.runner._PAYLOAD_SCHEMAS", {"deploy": DeployPayload}),
        patch("src.worker.runner.AsyncSessionLocal", return_value=mock_session),
        patch("src.worker.runner._mark_done", new=AsyncMock()) as mock_done,
        patch("src.worker.runner._mark_failed", new=AsyncMock()) as mock_failed,
    ):
        await _dispatch_job(job)

    mock_handler.assert_not_awaited()
    mock_done.assert_not_awaited()
    mock_failed.assert_awaited_once()
    error_msg = mock_failed.await_args.args[2]
    assert "invalid payload" in error_msg


@pytest.mark.asyncio
async def test_dispatch_job_valid_payload_passes_schema_and_calls_handler() -> None:
    """A job with a valid payload passes schema validation and reaches the handler."""
    from src.worker.payloads import DeployPayload

    generation_id = uuid.uuid4()
    job_id = uuid.uuid4()
    job = {
        "id": job_id,
        "kind": "deploy",
        "payload": {"generation_id": str(generation_id)},
        "owner_user_id": uuid.uuid4(),
        "attempts": 1,
    }

    mock_handler = AsyncMock(return_value={"ok": True})
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("src.worker.runner._HANDLERS", {"deploy": mock_handler}),
        patch("src.worker.runner._PAYLOAD_SCHEMAS", {"deploy": DeployPayload}),
        patch("src.worker.runner.AsyncSessionLocal", return_value=mock_session),
        patch("src.worker.runner._mark_done", new=AsyncMock()) as mock_done,
        patch("src.worker.runner._mark_failed", new=AsyncMock()) as mock_failed,
    ):
        await _dispatch_job(job)

    mock_handler.assert_awaited_once()
    mock_done.assert_awaited_once()
    mock_failed.assert_not_awaited()


# ── _reset_stale logging ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_reset_stale_logs_when_stale_jobs_found(mock_db: AsyncMock, caplog) -> None:
    """_reset_stale logs the count when stale rows are actually reset."""
    import logging
    mock_db.execute.return_value = MagicMock(fetchall=MagicMock(return_value=[(1,), (2,)]))

    with caplog.at_level(logging.INFO, logger="src.worker.runner"):
        await _reset_stale(mock_db)

    assert "2" in caplog.text
    assert "stale" in caplog.text.lower()


# ── _update_heartbeat ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_heartbeat_executes_and_commits(mock_db: AsyncMock) -> None:
    """_update_heartbeat runs an UPDATE and commits."""
    await _update_heartbeat(mock_db)
    mock_db.execute.assert_awaited_once()
    mock_db.commit.assert_awaited_once()
    sql = str(mock_db.execute.await_args.args[0])
    assert "worker_heartbeat" in sql


# ── _heartbeat_loop ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_heartbeat_loop_success_resets_failure_counter() -> None:
    """A successful heartbeat update resets the failure counter to 0."""
    import src.worker.runner as runner_mod

    runner_mod._heartbeat_failures = 2  # pre-seed with failures

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()

    async def fake_sleep(n):
        raise asyncio.CancelledError  # exit after one iteration

    with (
        patch("src.worker.runner.AsyncSessionLocal", return_value=mock_session),
        patch("src.worker.runner.asyncio.sleep", side_effect=fake_sleep),
    ):
        with pytest.raises(asyncio.CancelledError):
            await _heartbeat_loop()

    assert runner_mod._heartbeat_failures == 0


@pytest.mark.asyncio
async def test_heartbeat_loop_failure_increments_counter() -> None:
    """A failed heartbeat update increments _heartbeat_failures."""
    import src.worker.runner as runner_mod

    runner_mod._heartbeat_failures = 0

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.execute = AsyncMock(side_effect=RuntimeError("DB down"))
    mock_session.commit = AsyncMock()

    async def fake_sleep(n):
        raise asyncio.CancelledError

    with (
        patch("src.worker.runner.AsyncSessionLocal", return_value=mock_session),
        patch("src.worker.runner.asyncio.sleep", side_effect=fake_sleep),
    ):
        with pytest.raises(asyncio.CancelledError):
            await _heartbeat_loop()

    assert runner_mod._heartbeat_failures == 1


@pytest.mark.asyncio
async def test_heartbeat_loop_max_failures_calls_exit() -> None:
    """When failures reach MAX_HEARTBEAT_FAILURES, os._exit(1) is called."""
    import src.worker.runner as runner_mod

    runner_mod._heartbeat_failures = runner_mod.MAX_HEARTBEAT_FAILURES - 1

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.execute = AsyncMock(side_effect=RuntimeError("DB down"))
    mock_session.commit = AsyncMock()

    async def fake_sleep(n):
        raise asyncio.CancelledError  # unreachable but safe

    with (
        patch("src.worker.runner.AsyncSessionLocal", return_value=mock_session),
        patch("src.worker.runner.asyncio.sleep", side_effect=fake_sleep),
        patch("src.worker.runner.os._exit") as mock_exit,
    ):
        with pytest.raises(asyncio.CancelledError):
            await _heartbeat_loop()

    mock_exit.assert_called_once_with(1)


# ── _stale_reset_loop ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_stale_reset_loop_calls_reset_stale() -> None:
    """_stale_reset_loop calls _reset_stale once per iteration.

    The loop body is: sleep → reset_stale. We allow the first sleep through
    so _reset_stale runs, then cancel on the second sleep.
    """
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.execute = AsyncMock(
        return_value=MagicMock(fetchall=MagicMock(return_value=[]))
    )
    mock_session.commit = AsyncMock()

    sleep_count = 0

    async def fake_sleep(n):
        nonlocal sleep_count
        sleep_count += 1
        if sleep_count >= 2:
            raise asyncio.CancelledError  # exit after one full iteration

    with (
        patch("src.worker.runner.AsyncSessionLocal", return_value=mock_session),
        patch("src.worker.runner.asyncio.sleep", side_effect=fake_sleep),
    ):
        with pytest.raises(asyncio.CancelledError):
            await _stale_reset_loop()

    mock_session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_stale_reset_loop_swallows_exception() -> None:
    """Exceptions inside the loop body are swallowed; the loop continues."""
    call_count = 0

    async def fake_sleep(n):
        nonlocal call_count
        call_count += 1
        if call_count >= 2:
            raise asyncio.CancelledError  # exit after second sleep

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.execute = AsyncMock(side_effect=RuntimeError("DB error"))

    with (
        patch("src.worker.runner.AsyncSessionLocal", return_value=mock_session),
        patch("src.worker.runner.asyncio.sleep", side_effect=fake_sleep),
    ):
        with pytest.raises(asyncio.CancelledError):
            await _stale_reset_loop()

    assert call_count == 2  # loop continued after exception


# ── _experiment_loop ──────────────────────────────────────────────────────────


def _make_exp_result(converged: bool, winner_variant: str | None, confidence: float = 0.97):
    r = MagicMock()
    r.converged = converged
    r.winner_variant = winner_variant
    r.confidence = confidence
    return r


@pytest.mark.asyncio
async def test_experiment_loop_no_experiments_does_nothing() -> None:
    """When there are no running experiments, the loop body does nothing."""
    from src.worker.runner import _experiment_loop

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    async def fake_sleep(n):
        raise asyncio.CancelledError

    with (
        patch("src.worker.runner.AsyncSessionLocal", return_value=mock_session),
        patch("src.worker.runner.asyncio.sleep", side_effect=fake_sleep),
        patch("src.loop.experiment.repository.get_all_running_experiments", new=AsyncMock(return_value=[])),
    ):
        with pytest.raises(asyncio.CancelledError):
            await _experiment_loop()

    mock_session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_experiment_loop_not_converged_updates_stats_no_evolve() -> None:
    """Running experiment that hasn't converged: stats updated, no EVOLVE job enqueued."""
    from src.worker.runner import _experiment_loop

    exp = {
        "id": uuid.uuid4(),
        "deployment_id": uuid.uuid4(),
        "baseline_variant": "baseline",
        "challenger_variant": "cot",
        "win_threshold": 0.1,
    }

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()

    sleep_count = 0

    async def fake_sleep(n):
        nonlocal sleep_count
        sleep_count += 1
        if sleep_count >= 2:
            raise asyncio.CancelledError

    with (
        patch("src.worker.runner.AsyncSessionLocal", return_value=mock_session),
        patch("src.worker.runner.asyncio.sleep", side_effect=fake_sleep),
        patch("src.loop.experiment.repository.get_all_running_experiments", new=AsyncMock(return_value=[exp])),
        patch("src.loop.experiment.repository.aggregate_variant_wins", new=AsyncMock(return_value=(3, 10, 4, 10, 0))),
        patch("src.loop.experiment.repository.update_experiment_stats", new=AsyncMock()),
        patch("src.loop.experiment.engine.check_experiment", return_value=_make_exp_result(False, None)),
    ):
        with pytest.raises(asyncio.CancelledError):
            await _experiment_loop()

    # No INSERT should have been called since experiment didn't converge
    mock_session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_experiment_loop_converged_enqueues_evolve_job() -> None:
    """Converged experiment: EVOLVE job is INSERT-ed into verum_jobs."""
    from src.worker.runner import _experiment_loop

    owner_uid = uuid.uuid4()
    deployment_id = uuid.uuid4()
    exp = {
        "id": uuid.uuid4(),
        "deployment_id": deployment_id,
        "baseline_variant": "baseline",
        "challenger_variant": "cot",
        "win_threshold": 0.1,
    }

    owner_row_mock = MagicMock()
    owner_row_mock.__getitem__ = MagicMock(return_value=owner_uid)

    execute_result = MagicMock()
    execute_result.mappings.return_value.first.return_value = {"owner_user_id": owner_uid}

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.execute = AsyncMock(return_value=execute_result)
    mock_session.commit = AsyncMock()

    sleep_count = 0

    async def fake_sleep(n):
        nonlocal sleep_count
        sleep_count += 1
        if sleep_count >= 2:
            raise asyncio.CancelledError

    with (
        patch("src.worker.runner.AsyncSessionLocal", return_value=mock_session),
        patch("src.worker.runner.asyncio.sleep", side_effect=fake_sleep),
        patch("src.loop.experiment.repository.get_all_running_experiments", new=AsyncMock(return_value=[exp])),
        patch("src.loop.experiment.repository.aggregate_variant_wins", new=AsyncMock(return_value=(8, 10, 2, 10, 0))),
        patch("src.loop.experiment.repository.update_experiment_stats", new=AsyncMock()),
        patch("src.loop.experiment.engine.check_experiment", return_value=_make_exp_result(True, "baseline", 0.97)),
    ):
        with pytest.raises(asyncio.CancelledError):
            await _experiment_loop()

    # The INSERT into verum_jobs should have been called
    mock_session.execute.assert_awaited()
    insert_call_sql = str(mock_session.execute.await_args_list[-1].args[0])
    assert "verum_jobs" in insert_call_sql


@pytest.mark.asyncio
async def test_experiment_loop_converged_no_owner_logs_warning() -> None:
    """Converged experiment with no owner_user_id: inner error is swallowed (logged as warning)."""
    from src.worker.runner import _experiment_loop

    exp = {
        "id": uuid.uuid4(),
        "deployment_id": uuid.uuid4(),
        "baseline_variant": "baseline",
        "challenger_variant": "cot",
        "win_threshold": 0.1,
    }

    execute_result = MagicMock()
    execute_result.mappings.return_value.first.return_value = None  # no owner row

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.execute = AsyncMock(return_value=execute_result)
    mock_session.commit = AsyncMock()

    sleep_count = 0

    async def fake_sleep(n):
        nonlocal sleep_count
        sleep_count += 1
        if sleep_count >= 2:
            raise asyncio.CancelledError

    with (
        patch("src.worker.runner.AsyncSessionLocal", return_value=mock_session),
        patch("src.worker.runner.asyncio.sleep", side_effect=fake_sleep),
        patch("src.loop.experiment.repository.get_all_running_experiments", new=AsyncMock(return_value=[exp])),
        patch("src.loop.experiment.repository.aggregate_variant_wins", new=AsyncMock(return_value=(8, 10, 2, 10, 0))),
        patch("src.loop.experiment.repository.update_experiment_stats", new=AsyncMock()),
        patch("src.loop.experiment.engine.check_experiment", return_value=_make_exp_result(True, "baseline", 0.97)),
    ):
        # Should not raise — inner exception is swallowed
        with pytest.raises(asyncio.CancelledError):
            await _experiment_loop()

    # commit should NOT be called since the RuntimeError aborts before INSERT
    mock_session.commit.assert_not_awaited()
