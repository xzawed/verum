"""Unit tests for the EVOLVE stage repository (src.loop.evolve.repository)."""
from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, call

import pytest


# ---------------------------------------------------------------------------
# update_deployment_baseline
# ---------------------------------------------------------------------------

async def test_update_deployment_baseline_executes_and_commits(
    mock_db: AsyncMock,
) -> None:
    """update_deployment_baseline runs one UPDATE and commits."""
    from src.loop.evolve.repository import update_deployment_baseline

    dep_id = uuid.uuid4()
    await update_deployment_baseline(mock_db, dep_id, new_baseline="variant_cot")

    mock_db.execute.assert_awaited_once()
    mock_db.commit.assert_awaited_once()


async def test_update_deployment_baseline_passes_correct_params(
    mock_db: AsyncMock,
) -> None:
    """update_deployment_baseline passes the correct deployment_id and baseline variant."""
    from src.loop.evolve.repository import update_deployment_baseline

    dep_id = uuid.uuid4()
    new_baseline = "variant_cot"

    await update_deployment_baseline(mock_db, dep_id, new_baseline=new_baseline)

    params = mock_db.execute.call_args.args[1]
    assert params["bv"] == new_baseline
    assert params["did"] == str(dep_id)


# ---------------------------------------------------------------------------
# update_traffic_split
# ---------------------------------------------------------------------------

async def test_update_traffic_split_serializes_to_jsonb(mock_db: AsyncMock) -> None:
    """update_traffic_split passes the split as a JSON string in params."""
    from src.loop.evolve.repository import update_traffic_split

    dep_id = uuid.uuid4()
    split = {"baseline": 0.6, "variant": 0.4}

    await update_traffic_split(mock_db, dep_id, split=split)

    params = mock_db.execute.call_args.args[1]
    roundtripped = json.loads(params["split"])
    assert roundtripped["baseline"] == pytest.approx(0.6)
    assert roundtripped["variant"] == pytest.approx(0.4)
    mock_db.commit.assert_awaited_once()


async def test_update_traffic_split_sum_equals_one(mock_db: AsyncMock) -> None:
    """Traffic splits that don't sum to 1.0 are passed through unchanged (validation is caller's job)."""
    from src.loop.evolve.repository import update_traffic_split

    dep_id = uuid.uuid4()
    split = {"baseline": 1.0, "variant": 0.0}

    await update_traffic_split(mock_db, dep_id, split=split)

    params = mock_db.execute.call_args.args[1]
    data = json.loads(params["split"])
    total = data["baseline"] + data["variant"]
    assert total == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# set_experiment_status
# ---------------------------------------------------------------------------

async def test_set_experiment_status_running(mock_db: AsyncMock) -> None:
    """set_experiment_status('running') passes status='running' in params."""
    from src.loop.evolve.repository import set_experiment_status

    dep_id = uuid.uuid4()
    await set_experiment_status(mock_db, dep_id, status="running")

    params = mock_db.execute.call_args.args[1]
    assert params["s"] == "running"
    assert params["did"] == str(dep_id)
    mock_db.commit.assert_awaited_once()


async def test_set_experiment_status_completed(mock_db: AsyncMock) -> None:
    """set_experiment_status('completed') writes 'completed' status."""
    from src.loop.evolve.repository import set_experiment_status

    dep_id = uuid.uuid4()
    await set_experiment_status(mock_db, dep_id, status="completed")

    params = mock_db.execute.call_args.args[1]
    assert params["s"] == "completed"


async def test_set_experiment_status_idle(mock_db: AsyncMock) -> None:
    """set_experiment_status('idle') writes 'idle' status."""
    from src.loop.evolve.repository import set_experiment_status

    dep_id = uuid.uuid4()
    await set_experiment_status(mock_db, dep_id, status="idle")

    params = mock_db.execute.call_args.args[1]
    assert params["s"] == "idle"
