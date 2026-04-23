"""Tests for the EVOLVE stage engine ([8] of The Verum Loop)."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from src.loop.evolve.engine import (
    complete_deployment,
    next_challenger,
    promote_winner,
    start_next_challenger,
)
from src.loop.experiment.engine import CHALLENGER_ORDER


# ---------------------------------------------------------------------------
# next_challenger — pure function, no DB
# ---------------------------------------------------------------------------

def test_next_challenger_first_round() -> None:
    """cot is the first challenger; next is few_shot."""
    assert next_challenger("original", "cot") == "few_shot"


def test_next_challenger_mid_sequence() -> None:
    """few_shot → role_play when both exist in CHALLENGER_ORDER."""
    result = next_challenger("original", "few_shot")
    idx = CHALLENGER_ORDER.index("few_shot")
    assert result == CHALLENGER_ORDER[idx + 1]


def test_next_challenger_returns_none_at_end() -> None:
    """Last challenger has no successor — returns None."""
    last = CHALLENGER_ORDER[-1]
    assert next_challenger("original", last) is None


def test_next_challenger_returns_none_for_unknown_challenger() -> None:
    """Unknown challenger name that isn't in CHALLENGER_ORDER → None."""
    assert next_challenger("original", "totally_unknown_variant") is None


# ---------------------------------------------------------------------------
# promote_winner — calls mark_experiment_converged + update_deployment_baseline
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_promote_winner_calls_both_repo_functions() -> None:
    """promote_winner delegates to mark_experiment_converged and update_deployment_baseline."""
    db = AsyncMock()
    experiment_id = uuid.uuid4()
    deployment_id = uuid.uuid4()

    with (
        patch(
            "src.loop.evolve.engine.mark_experiment_converged",
            new_callable=AsyncMock,
        ) as mock_converged,
        patch(
            "src.loop.evolve.engine.update_deployment_baseline",
            new_callable=AsyncMock,
        ) as mock_baseline,
    ):
        await promote_winner(db, experiment_id, deployment_id, "cot", 0.97)

    mock_converged.assert_awaited_once_with(db, experiment_id, "cot", 0.97)
    mock_baseline.assert_awaited_once_with(db, deployment_id, "cot")


@pytest.mark.asyncio
async def test_promote_winner_propagates_db_error() -> None:
    """If update_deployment_baseline raises, the exception propagates."""
    db = AsyncMock()

    with (
        patch(
            "src.loop.evolve.engine.mark_experiment_converged",
            new_callable=AsyncMock,
        ),
        patch(
            "src.loop.evolve.engine.update_deployment_baseline",
            side_effect=RuntimeError("DB error"),
        ),
    ):
        with pytest.raises(RuntimeError, match="DB error"):
            await promote_winner(db, uuid.uuid4(), uuid.uuid4(), "cot", 0.97)


# ---------------------------------------------------------------------------
# start_next_challenger — inserts experiment + updates traffic split
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_start_next_challenger_returns_true_and_inserts() -> None:
    """When a next challenger exists, inserts experiment and updates split."""
    db = AsyncMock()
    deployment_id = uuid.uuid4()

    with (
        patch(
            "src.loop.evolve.engine.insert_experiment",
            new_callable=AsyncMock,
        ) as mock_insert,
        patch(
            "src.loop.evolve.engine.update_traffic_split",
            new_callable=AsyncMock,
        ) as mock_split,
    ):
        result = await start_next_challenger(db, deployment_id, "original", "cot")

    assert result is True
    mock_insert.assert_awaited_once_with(db, deployment_id, "original", "few_shot")
    mock_split.assert_awaited_once_with(
        db, deployment_id, {"original": 0.9, "few_shot": 0.1}
    )


@pytest.mark.asyncio
async def test_start_next_challenger_returns_false_when_all_done() -> None:
    """When current_challenger is the last variant, returns False without DB calls."""
    db = AsyncMock()
    last = CHALLENGER_ORDER[-1]

    with (
        patch(
            "src.loop.evolve.engine.insert_experiment",
            new_callable=AsyncMock,
        ) as mock_insert,
        patch(
            "src.loop.evolve.engine.update_traffic_split",
            new_callable=AsyncMock,
        ) as mock_split,
    ):
        result = await start_next_challenger(db, uuid.uuid4(), "original", last)

    assert result is False
    mock_insert.assert_not_awaited()
    mock_split.assert_not_awaited()


@pytest.mark.asyncio
async def test_start_next_challenger_winner_is_new_baseline() -> None:
    """The new traffic split uses winner_variant as 90% baseline."""
    db = AsyncMock()
    deployment_id = uuid.uuid4()

    with (
        patch("src.loop.evolve.engine.insert_experiment", new_callable=AsyncMock),
        patch(
            "src.loop.evolve.engine.update_traffic_split",
            new_callable=AsyncMock,
        ) as mock_split,
    ):
        await start_next_challenger(db, deployment_id, "cot", "few_shot")

    call_kwargs = mock_split.await_args
    split_arg = call_kwargs.args[2]
    assert split_arg.get("cot") == 0.9
    assert 0.0 < list(split_arg.values())[1] <= 0.1


# ---------------------------------------------------------------------------
# complete_deployment — 100% traffic + status=completed
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_complete_deployment_sets_full_traffic_and_status() -> None:
    """complete_deployment routes 100% to winner and marks experiment completed."""
    db = AsyncMock()
    deployment_id = uuid.uuid4()

    with (
        patch(
            "src.loop.evolve.engine.update_traffic_split",
            new_callable=AsyncMock,
        ) as mock_split,
        patch(
            "src.loop.evolve.engine.set_experiment_status",
            new_callable=AsyncMock,
        ) as mock_status,
    ):
        await complete_deployment(db, deployment_id, "role_play")

    mock_split.assert_awaited_once_with(db, deployment_id, {"role_play": 1.0})
    mock_status.assert_awaited_once_with(db, deployment_id, "completed")
