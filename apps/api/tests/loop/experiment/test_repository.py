"""Unit tests for the EXPERIMENT stage repository (src.loop.experiment.repository)."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row(variant: str, wins: int, n: int, null_score_count: int = 0) -> dict:
    return {
        "variant": variant,
        "wins": wins,
        "n": n,
        "null_score_count": null_score_count,
    }


# ---------------------------------------------------------------------------
# get_running_experiment
# ---------------------------------------------------------------------------

async def test_get_running_experiment_returns_none_when_missing(
    mock_db: AsyncMock,
) -> None:
    """Returns None when no running experiment exists for the deployment."""
    from src.loop.experiment.repository import get_running_experiment

    result_mock = MagicMock()
    result_mock.mappings.return_value.first.return_value = None
    mock_db.execute = AsyncMock(return_value=result_mock)

    result = await get_running_experiment(mock_db, uuid.uuid4())
    assert result is None


async def test_get_running_experiment_returns_dict_when_found(
    mock_db: AsyncMock,
) -> None:
    """Returns a dict representation of the experiment row when it exists."""
    from src.loop.experiment.repository import get_running_experiment

    exp_id = uuid.uuid4()
    dep_id = uuid.uuid4()
    row = {
        "id": str(exp_id),
        "deployment_id": str(dep_id),
        "status": "running",
        "baseline_variant": "baseline",
        "challenger_variant": "variant_cot",
    }
    result_mock = MagicMock()
    result_mock.mappings.return_value.first.return_value = row
    mock_db.execute = AsyncMock(return_value=result_mock)

    result = await get_running_experiment(mock_db, dep_id)
    assert result is not None
    assert result["status"] == "running"


# ---------------------------------------------------------------------------
# get_all_running_experiments
# ---------------------------------------------------------------------------

async def test_get_all_running_experiments_returns_empty_list(
    mock_db: AsyncMock,
) -> None:
    """Returns [] when no experiments are running across all deployments."""
    from src.loop.experiment.repository import get_all_running_experiments

    result_mock = MagicMock()
    result_mock.mappings.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=result_mock)

    result = await get_all_running_experiments(mock_db)
    assert result == []


# ---------------------------------------------------------------------------
# update_experiment_stats
# ---------------------------------------------------------------------------

async def test_update_experiment_stats_commits(mock_db: AsyncMock) -> None:
    """update_experiment_stats executes UPDATE with all 5 counters and commits."""
    from src.loop.experiment.repository import update_experiment_stats

    exp_id = uuid.uuid4()
    await update_experiment_stats(mock_db, exp_id, 15, 20, 12, 20)

    mock_db.execute.assert_awaited_once()
    mock_db.commit.assert_awaited_once()

    params = mock_db.execute.call_args.args[1]
    assert params["bw"] == 15
    assert params["bn"] == 20
    assert params["cw"] == 12
    assert params["cn"] == 20
    assert params["eid"] == str(exp_id)


# ---------------------------------------------------------------------------
# insert_experiment
# ---------------------------------------------------------------------------

async def test_insert_experiment_returns_dict_with_running_status(
    mock_db: AsyncMock,
) -> None:
    """insert_experiment inserts a new row and returns it as a dict."""
    from src.loop.experiment.repository import insert_experiment

    dep_id = uuid.uuid4()
    exp_id = uuid.uuid4()
    row = {
        "id": str(exp_id),
        "deployment_id": str(dep_id),
        "status": "running",
        "baseline_variant": "baseline",
        "challenger_variant": "variant_cot",
        "baseline_wins": 0,
        "baseline_n": 0,
        "challenger_wins": 0,
        "challenger_n": 0,
    }
    result_mock = MagicMock()
    result_mock.mappings.return_value.first.return_value = row
    mock_db.execute = AsyncMock(return_value=result_mock)

    result = await insert_experiment(mock_db, dep_id, "baseline", "variant_cot")

    assert result["status"] == "running"
    assert result["baseline_variant"] == "baseline"
    mock_db.commit.assert_awaited_once()


async def test_insert_experiment_raises_when_insert_returns_no_row(
    mock_db: AsyncMock,
) -> None:
    """insert_experiment raises RuntimeError when INSERT RETURNING yields nothing."""
    from src.loop.experiment.repository import insert_experiment

    result_mock = MagicMock()
    result_mock.mappings.return_value.first.return_value = None
    mock_db.execute = AsyncMock(return_value=result_mock)

    with pytest.raises(RuntimeError):
        await insert_experiment(mock_db, uuid.uuid4(), "baseline", "variant_cot")


# ---------------------------------------------------------------------------
# mark_experiment_converged
# ---------------------------------------------------------------------------

async def test_mark_experiment_converged_commits(mock_db: AsyncMock) -> None:
    """mark_experiment_converged executes UPDATE with correct params and commits."""
    from src.loop.experiment.repository import mark_experiment_converged

    exp_id = uuid.uuid4()
    await mark_experiment_converged(mock_db, exp_id, "variant_cot", confidence=0.97)

    mock_db.execute.assert_awaited_once()
    mock_db.commit.assert_awaited_once()

    params = mock_db.execute.call_args.args[1]
    assert params["wv"] == "variant_cot"
    assert params["conf"] == pytest.approx(0.97)
    assert params["eid"] == str(exp_id)


# ---------------------------------------------------------------------------
# aggregate_variant_wins — SQL param contract
# ---------------------------------------------------------------------------

async def test_aggregate_variant_wins_passes_correct_params(
    mock_db: AsyncMock,
) -> None:
    """aggregate_variant_wins binds deployment_id, variant names, threshold as params."""
    from src.loop.experiment.repository import aggregate_variant_wins

    dep_id = uuid.uuid4()

    # First execute: max_cost query → returns 0
    max_cost_row = {"max_cost": 0}
    max_cost_result = MagicMock()
    max_cost_result.mappings.return_value.first.return_value = max_cost_row

    # Second execute: variant win aggregation → empty (no traces)
    agg_result = MagicMock()
    agg_result.mappings.return_value.all.return_value = []

    mock_db.execute = AsyncMock(side_effect=[max_cost_result, agg_result])

    bw, bn, cw, cn, nulls = await aggregate_variant_wins(
        mock_db, dep_id, "baseline", "variant_cot", win_threshold=0.5
    )

    assert bw == 0
    assert bn == 0
    assert cw == 0
    assert cn == 0
    assert nulls == 0

    second_call_params = mock_db.execute.call_args_list[1].args[1]
    assert second_call_params["did"] == str(dep_id)
    assert second_call_params["bv"] == "baseline"
    assert second_call_params["cv"] == "variant_cot"
    assert second_call_params["threshold"] == pytest.approx(0.5)


async def test_aggregate_variant_wins_counts_correctly_from_db_rows(
    mock_db: AsyncMock,
) -> None:
    """aggregate_variant_wins tallies wins/n per variant from aggregated rows."""
    from src.loop.experiment.repository import aggregate_variant_wins

    dep_id = uuid.uuid4()

    max_cost_result = MagicMock()
    max_cost_result.mappings.return_value.first.return_value = {"max_cost": 0.01}

    agg_rows = [
        _row("baseline", wins=8, n=10),
        _row("variant_cot", wins=5, n=10, null_score_count=2),
    ]
    agg_result = MagicMock()
    agg_result.mappings.return_value.all.return_value = agg_rows

    mock_db.execute = AsyncMock(side_effect=[max_cost_result, agg_result])

    bw, bn, cw, cn, nulls = await aggregate_variant_wins(
        mock_db, dep_id, "baseline", "variant_cot", win_threshold=0.5
    )

    assert bw == 8
    assert bn == 10
    assert cw == 5
    assert cn == 10
    assert nulls == 2
