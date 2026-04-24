"""Tests for observe repository. Unit tests use AsyncMock; DB tests require live DB."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.loop.observe.models import TraceRecord, SpanRecord
from src.db.models.traces import Trace


def test_trace_record_defaults():
    rec = TraceRecord(
        deployment_id=uuid.uuid4(),
        variant="cot",
        model="grok-2-1212",
        input_tokens=512,
        output_tokens=284,
        latency_ms=980,
    )
    assert rec.error is None
    assert rec.cost_usd == 0.0


def test_span_record_cost_calculation():
    rec = SpanRecord(
        trace_id=uuid.uuid4(),
        model="grok-2-1212",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        latency_ms=1000,
        cost_usd=12.0,  # 2.0 input + 10.0 output
    )
    assert rec.cost_usd == 12.0


def test_trace_model_import():
    assert Trace.__tablename__ == "traces"


from src.loop.observe.repository import calculate_cost


def test_calculate_cost_known_model():
    # 1M input + 1M output of grok-2-1212 = 2.00 + 10.00 = 12.00
    pricing = {"input_per_1m_usd": 2.0, "output_per_1m_usd": 10.0}
    cost = calculate_cost(
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        pricing=pricing,
    )
    assert abs(cost - 12.0) < 0.0001


def test_calculate_cost_none_for_no_pricing():
    cost = calculate_cost(input_tokens=500, output_tokens=300, pricing=None)
    assert cost is None


def test_calculate_cost_rounds_to_six_places():
    pricing = {"input_per_1m_usd": 1.0, "output_per_1m_usd": 1.0}
    cost = calculate_cost(input_tokens=1, output_tokens=1, pricing=pricing)
    # 1/1_000_000 + 1/1_000_000 = 0.000002
    assert cost == pytest.approx(0.000002, rel=1e-5)


# ---------------------------------------------------------------------------
# Mock-based unit tests for async DB functions
# ---------------------------------------------------------------------------

from src.loop.observe.repository import (
    _get_pricing,
    get_daily_metrics,
    insert_trace,
    update_judge_score,
    update_user_feedback,
)


def _mock_db() -> AsyncMock:
    db = AsyncMock()
    db.commit = AsyncMock()
    db.execute = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_get_pricing_returns_dict_when_found():
    db = _mock_db()
    fake_row = {"input_per_1m_usd": 3.0, "output_per_1m_usd": 15.0}
    result_mock = MagicMock()
    result_mock.mappings.return_value.first.return_value = fake_row
    db.execute.return_value = result_mock

    pricing = await _get_pricing(db, "claude-sonnet-4-6")
    assert pricing == {"input_per_1m_usd": 3.0, "output_per_1m_usd": 15.0}


@pytest.mark.asyncio
async def test_get_pricing_returns_none_when_not_found():
    db = _mock_db()
    result_mock = MagicMock()
    result_mock.mappings.return_value.first.return_value = None
    db.execute.return_value = result_mock

    pricing = await _get_pricing(db, "unknown-model-xyz")
    assert pricing is None


@pytest.mark.asyncio
async def test_insert_trace_returns_uuid():
    db = _mock_db()
    no_pricing_result = MagicMock()
    no_pricing_result.mappings.return_value.first.return_value = None
    db.execute.return_value = no_pricing_result

    record = TraceRecord(
        deployment_id=uuid.uuid4(),
        variant="baseline",
        model="grok-2-1212",
        input_tokens=100,
        output_tokens=50,
        latency_ms=500,
    )
    trace_id = await insert_trace(db, record)
    assert isinstance(trace_id, uuid.UUID)
    db.commit.assert_awaited_once()
    assert db.execute.call_count == 3  # _get_pricing + INSERT traces + INSERT spans


@pytest.mark.asyncio
async def test_update_judge_score_commits():
    db = _mock_db()
    await update_judge_score(db, uuid.uuid4(), 0.85, "prompt text", '{"score": 0.85}')
    db.commit.assert_awaited_once()
    assert db.execute.call_count == 2  # UPDATE traces + INSERT judge_prompts


@pytest.mark.asyncio
async def test_update_user_feedback_returns_true_on_match():
    db = _mock_db()
    result_mock = MagicMock()
    result_mock.rowcount = 1

    with patch("src.loop.observe.repository.execute_commit", new=AsyncMock(return_value=result_mock)):
        found = await update_user_feedback(db, uuid.uuid4(), 1)
    assert found is True


@pytest.mark.asyncio
async def test_update_user_feedback_returns_false_when_not_found():
    db = _mock_db()
    result_mock = MagicMock()
    result_mock.rowcount = 0

    with patch("src.loop.observe.repository.execute_commit", new=AsyncMock(return_value=result_mock)):
        found = await update_user_feedback(db, uuid.uuid4(), -1)
    assert found is False


@pytest.mark.asyncio
async def test_get_daily_metrics_returns_list():
    db = _mock_db()
    fake_rows = [
        {"date": "2026-04-20", "total_cost_usd": 0.05, "call_count": 10,
         "p95_latency_ms": 800, "avg_judge_score": 0.75},
        {"date": "2026-04-21", "total_cost_usd": 0.12, "call_count": 25,
         "p95_latency_ms": 950, "avg_judge_score": None},
    ]
    result_mock = MagicMock()
    result_mock.mappings.return_value.all.return_value = fake_rows
    db.execute.return_value = result_mock

    metrics = await get_daily_metrics(db, uuid.uuid4(), days=7)
    assert len(metrics) == 2
    assert metrics[0].call_count == 10
    assert metrics[1].avg_judge_score is None
