"""Tests for the DEPLOY job handler and deploy orchestrator atomicity."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from src.loop.deploy.models import DeploymentWithKey
from src.worker.handlers.deploy import handle_deploy, _write_integration_state


def _make_deployment(generation_id: uuid.UUID | None = None) -> DeploymentWithKey:
    now = datetime.now(tz=timezone.utc)
    return DeploymentWithKey(
        deployment_id=uuid.uuid4(),
        generation_id=generation_id or uuid.uuid4(),
        status="canary",
        traffic_split={"baseline": 0.9, "variant": 0.1},
        error_count=0,
        total_calls=0,
        created_at=now,
        updated_at=now,
        api_key="test_api_key_abc123",
    )


# ---------------------------------------------------------------------------
# Atomicity: handler owns the final commit
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handle_deploy_commits_after_orchestrator() -> None:
    """db.commit() is called by the handler, not inside deploy_and_start_experiment."""
    db = AsyncMock()
    generation_id = uuid.uuid4()
    experiment_id = uuid.uuid4()
    deployment = _make_deployment(generation_id)

    commit_calls: list[str] = []

    async def _fake_orchestrator(db_, gid, *, variant_fraction=0.10):
        commit_calls.append("orchestrator_returned")
        return deployment, experiment_id

    async def _fake_commit():
        commit_calls.append("commit")

    db.commit = AsyncMock(side_effect=_fake_commit)

    with patch(
        "src.worker.handlers.deploy.deploy_and_start_experiment",
        side_effect=_fake_orchestrator,
    ):
        await handle_deploy(db, uuid.uuid4(), {"generation_id": str(generation_id)})

    assert commit_calls == ["orchestrator_returned", "commit"], (
        "db.commit() must be called AFTER deploy_and_start_experiment returns — "
        "not inside the orchestrator"
    )


@pytest.mark.asyncio
async def test_handle_deploy_does_not_commit_on_orchestrator_error() -> None:
    """If deploy_and_start_experiment raises, db.commit() must not be called."""
    db = AsyncMock()

    with patch(
        "src.worker.handlers.deploy.deploy_and_start_experiment",
        side_effect=RuntimeError("INSERT returned no row"),
    ):
        with pytest.raises(RuntimeError, match="INSERT returned no row"):
            await handle_deploy(db, uuid.uuid4(), {"generation_id": str(uuid.uuid4())})

    db.commit.assert_not_awaited()


# ---------------------------------------------------------------------------
# Return value shape
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handle_deploy_return_dict_shape() -> None:
    """Return dict contains deployment_id, status, traffic_split."""
    db = AsyncMock()
    generation_id = uuid.uuid4()
    deployment = _make_deployment(generation_id)

    with patch(
        "src.worker.handlers.deploy.deploy_and_start_experiment",
        return_value=(deployment, uuid.uuid4()),
        new_callable=AsyncMock,
    ):
        result = await handle_deploy(db, uuid.uuid4(), {"generation_id": str(generation_id)})

    assert result["deployment_id"] == str(deployment.deployment_id)
    assert result["status"] == "canary"
    assert result["traffic_split"] == {"baseline": 0.9, "variant": 0.1}


# ---------------------------------------------------------------------------
# Orchestrator: deploy_and_start_experiment does NOT commit
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deploy_and_start_experiment_does_not_commit() -> None:
    """The orchestrator must not call db.commit() — caller owns the transaction."""
    from src.loop.deploy.orchestrator import deploy_and_start_experiment

    db = AsyncMock()
    generation_id = uuid.uuid4()
    dep_id = uuid.uuid4()
    exp_id = uuid.uuid4()
    now = datetime.now(tz=timezone.utc)

    dep_row: dict[str, Any] = {
        "id": dep_id,
        "generation_id": generation_id,
        "status": "canary",
        "traffic_split": '{"baseline": 0.9, "variant": 0.1}',
        "error_count": 0,
        "total_calls": 0,
        "created_at": now,
        "updated_at": now,
    }
    exp_row: dict[str, Any] = {"id": exp_id}

    def _make_execute_result(row: dict | None):
        result = MagicMock()
        mappings = MagicMock()
        result.mappings.return_value = mappings
        mappings.first.return_value = row
        return result

    db.execute = AsyncMock(
        side_effect=[
            _make_execute_result(dep_row),
            _make_execute_result(exp_row),
        ]
    )

    deployment, returned_exp_id = await deploy_and_start_experiment(db, generation_id)

    db.commit.assert_not_awaited()
    assert deployment.status == "canary"
    assert str(returned_exp_id) == str(exp_id)


@pytest.mark.asyncio
async def test_deploy_and_start_experiment_raises_when_deployment_insert_fails() -> None:
    """RuntimeError is raised if the deployment INSERT returns no row."""
    from src.loop.deploy.orchestrator import deploy_and_start_experiment

    db = AsyncMock()

    result = MagicMock()
    result.mappings.return_value.first.return_value = None
    db.execute = AsyncMock(return_value=result)

    with pytest.raises(RuntimeError, match="deployment INSERT returned no row"):
        await deploy_and_start_experiment(db, uuid.uuid4())


@pytest.mark.asyncio
async def test_deploy_and_start_experiment_raises_when_experiment_insert_fails() -> None:
    """RuntimeError is raised if the experiment INSERT returns no row."""
    from src.loop.deploy.orchestrator import deploy_and_start_experiment

    db = AsyncMock()
    now = datetime.now(tz=timezone.utc)

    dep_row: dict[str, Any] = {
        "id": uuid.uuid4(),
        "generation_id": uuid.uuid4(),
        "status": "canary",
        "traffic_split": '{"baseline": 0.9, "variant": 0.1}',
        "error_count": 0,
        "total_calls": 0,
        "created_at": now,
        "updated_at": now,
    }

    def _make_execute_result(row: dict | None):
        result = MagicMock()
        result.mappings.return_value.first.return_value = row
        return result

    db.execute = AsyncMock(
        side_effect=[
            _make_execute_result(dep_row),
            _make_execute_result(None),
        ]
    )

    with pytest.raises(RuntimeError, match="experiment INSERT returned no row"):
        await deploy_and_start_experiment(db, uuid.uuid4())


# ---------------------------------------------------------------------------
# _write_integration_state — test-mode file output
# ---------------------------------------------------------------------------


def test_write_integration_state_writes_json(tmp_path) -> None:
    """_write_integration_state writes deployment_info.json with correct content."""
    import src.worker.handlers.deploy as deploy_module

    dep_id = uuid.uuid4()
    api_key = "sk-testkey123"

    original_dir = deploy_module._INTEGRATION_STATE_DIR
    deploy_module._INTEGRATION_STATE_DIR = tmp_path
    try:
        _write_integration_state(dep_id, api_key)
    finally:
        deploy_module._INTEGRATION_STATE_DIR = original_dir

    state_file = tmp_path / "deployment_info.json"
    assert state_file.exists()
    data = json.loads(state_file.read_text())
    assert data["deployment_id"] == str(dep_id)
    assert data["api_key"] == api_key


@pytest.mark.asyncio
async def test_handle_deploy_test_mode_writes_integration_state(tmp_path) -> None:
    """When _TEST_MODE is True, _write_integration_state is called after commit."""
    import src.worker.handlers.deploy as deploy_module

    db = AsyncMock()
    generation_id = uuid.uuid4()
    deployment = _make_deployment(generation_id)

    original_test_mode = deploy_module._TEST_MODE
    original_dir = deploy_module._INTEGRATION_STATE_DIR
    deploy_module._TEST_MODE = True
    deploy_module._INTEGRATION_STATE_DIR = tmp_path
    try:
        with patch(
            "src.worker.handlers.deploy.deploy_and_start_experiment",
            return_value=(deployment, uuid.uuid4()),
            new_callable=AsyncMock,
        ):
            result = await handle_deploy(db, uuid.uuid4(), {"generation_id": str(generation_id)})
    finally:
        deploy_module._TEST_MODE = original_test_mode
        deploy_module._INTEGRATION_STATE_DIR = original_dir

    state_file = tmp_path / "deployment_info.json"
    assert state_file.exists()
    data = json.loads(state_file.read_text())
    assert data["deployment_id"] == result["deployment_id"]
