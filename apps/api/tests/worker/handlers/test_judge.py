"""Tests for the judge handler."""
from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.worker.handlers.judge import _build_judge_prompt, _parse_judge_response, handle_judge


# ── Helper factories ──────────────────────────────────────────────────────────


def _scalar_result(value):
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    return r


def _mappings_first_result(row):
    r = MagicMock()
    r.mappings.return_value.first.return_value = row
    return r


def _mappings_all_result(rows):
    r = MagicMock()
    r.mappings.return_value.all.return_value = rows
    return r


def _make_db_for_judge(trace_mock, domain_row, pair_rows):
    """Build a mock_db whose execute calls return the three expected results in order."""
    db = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.execute = AsyncMock(side_effect=[
        _scalar_result(trace_mock),
        _mappings_first_result(domain_row),
        _mappings_all_result(pair_rows),
    ])
    return db


def test_build_judge_prompt_contains_domain():
    prompt = _build_judge_prompt(
        domain="divination/tarot",
        tone="mystical",
        eval_pairs=[
            {"query": "What does The Star mean?", "expected_answer": "Hope and renewal"},
        ],
    )
    assert "divination/tarot" in prompt
    assert "mystical" in prompt
    assert "The Star" in prompt


def test_parse_judge_response_valid():
    raw = json.dumps({"score": 0.82, "reason": "Good answer"})
    score, reason = _parse_judge_response(raw)
    assert abs(score - 0.82) < 0.001
    assert reason == "Good answer"


def test_parse_judge_response_clamped():
    raw = json.dumps({"score": 1.5, "reason": "Over limit"})
    score, _ = _parse_judge_response(raw)
    assert score == pytest.approx(1.0)


def test_parse_judge_response_invalid_returns_none():
    score, reason = _parse_judge_response("not json at all")
    assert score is None
    assert reason is None


def test_parse_judge_response_missing_score_key_returns_none():
    raw = json.dumps({"reason": "no score field"})
    score, reason = _parse_judge_response(raw)
    assert score is None
    assert reason is None


def test_parse_judge_response_clamps_below_zero():
    raw = json.dumps({"score": -0.5, "reason": "negative"})
    score, _ = _parse_judge_response(raw)
    assert score == pytest.approx(0.0)


# ── handle_judge integration tests ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_handle_judge_trace_not_found(owner_user_id: uuid.UUID) -> None:
    """Raises ValueError when the trace_id does not exist."""
    db = AsyncMock()
    db.commit = AsyncMock()
    db.execute = AsyncMock(return_value=_scalar_result(None))

    payload = {
        "trace_id": str(uuid.uuid4()),
        "deployment_id": str(uuid.uuid4()),
        "variant": "baseline",
    }
    with pytest.raises(ValueError, match="not found"):
        await handle_judge(db, owner_user_id, payload)


@pytest.mark.asyncio
async def test_handle_judge_already_scored_returns_skipped(owner_user_id: uuid.UUID) -> None:
    """Returns skipped=True when the trace already has a judge_score."""
    trace = MagicMock()
    trace.judge_score = 0.75

    db = AsyncMock()
    db.commit = AsyncMock()
    db.execute = AsyncMock(return_value=_scalar_result(trace))

    payload = {
        "trace_id": str(uuid.uuid4()),
        "deployment_id": str(uuid.uuid4()),
        "variant": "challenger",
    }
    result = await handle_judge(db, owner_user_id, payload)

    assert result["skipped"] is True
    assert "trace_id" in result


@pytest.mark.asyncio
async def test_handle_judge_happy_path_returns_score(owner_user_id: uuid.UUID) -> None:
    """Happy path: loads domain, calls LLM, persists score, returns result."""
    trace_id = uuid.uuid4()
    trace = MagicMock()
    trace.judge_score = None

    db = _make_db_for_judge(
        trace_mock=trace,
        domain_row={"domain": "divination/tarot", "tone": "mystical"},
        pair_rows=[{"query": "What is The Fool?", "expected_answer": "New beginnings"}],
    )

    raw_json = json.dumps({"score": 0.88, "reason": "Accurate tarot interpretation"})

    with (
        patch("src.worker.handlers.judge.call_claude", new=AsyncMock(return_value=raw_json)),
        patch("src.worker.handlers.judge.update_judge_score", new=AsyncMock()),
    ):
        result = await handle_judge(
            db,
            owner_user_id,
            {"trace_id": str(trace_id), "deployment_id": str(uuid.uuid4()), "variant": "cot"},
        )

    assert abs(result["judge_score"] - 0.88) < 0.001
    assert result["trace_id"] == str(trace_id)
    assert result["reason"] == "Accurate tarot interpretation"


@pytest.mark.asyncio
async def test_handle_judge_fallback_domain_when_no_row(owner_user_id: uuid.UUID) -> None:
    """Uses 'general'/'professional' defaults when deployment chain returns no domain row."""
    trace = MagicMock()
    trace.judge_score = None

    db = _make_db_for_judge(
        trace_mock=trace,
        domain_row=None,  # No deployment chain found
        pair_rows=[],
    )

    raw_json = json.dumps({"score": 0.5, "reason": "Generic answer"})

    with (
        patch("src.worker.handlers.judge.call_claude", new=AsyncMock(return_value=raw_json)),
        patch("src.worker.handlers.judge.update_judge_score", new=AsyncMock()) as mock_update,
    ):
        result = await handle_judge(
            db,
            owner_user_id,
            {"trace_id": str(uuid.uuid4()), "deployment_id": str(uuid.uuid4()), "variant": "baseline"},
        )

    assert result["judge_score"] == pytest.approx(0.5)
    mock_update.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_judge_all_retries_fail_raises_runtime_error(owner_user_id: uuid.UUID) -> None:
    """When all LLM parse attempts fail, RuntimeError is raised and global counter incremented."""
    import src.worker.handlers.judge as judge_mod

    trace = MagicMock()
    trace.judge_score = None

    db = _make_db_for_judge(
        trace_mock=trace,
        domain_row={"domain": "general", "tone": "professional"},
        pair_rows=[],
    )

    before = judge_mod._judge_parse_failures

    with (
        patch("src.worker.handlers.judge.call_claude", new=AsyncMock(return_value='{"bad": "no score"}')),
        patch("src.worker.handlers.judge.update_judge_score", new=AsyncMock()),
    ):
        with pytest.raises(RuntimeError, match="LLM judge evaluation failed"):
            await handle_judge(
                db,
                owner_user_id,
                {"trace_id": str(uuid.uuid4()), "deployment_id": str(uuid.uuid4()), "variant": "baseline"},
            )

    assert judge_mod._judge_parse_failures > before


@pytest.mark.asyncio
async def test_handle_judge_llm_exception_all_retries_raises(owner_user_id: uuid.UUID) -> None:
    """When call_claude raises on every attempt, RuntimeError is raised after retries."""
    trace = MagicMock()
    trace.judge_score = None

    db = _make_db_for_judge(
        trace_mock=trace,
        domain_row=None,
        pair_rows=[],
    )

    with (
        patch("src.worker.handlers.judge.call_claude", new=AsyncMock(side_effect=RuntimeError("LLM timeout"))),
        patch("src.worker.handlers.judge.update_judge_score", new=AsyncMock()),
    ):
        with pytest.raises(RuntimeError, match="LLM judge evaluation failed"):
            await handle_judge(
                db,
                owner_user_id,
                {"trace_id": str(uuid.uuid4()), "deployment_id": str(uuid.uuid4()), "variant": "baseline"},
            )
