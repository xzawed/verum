"""Unit tests for src.loop.deploy.orchestrator.deploy_and_start_experiment.

Covers behavior NOT already tested in tests/worker/handlers/test_deploy_handler.py:
- Return type is (DeploymentWithKey, UUID)
- Each call generates a unique raw API key
- The value stored in DB is the sha256 hash, not the raw key
- compute_traffic_split is called with the correct variant_fraction
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.loop.deploy.models import DeploymentWithKey
from src.loop.deploy.orchestrator import deploy_and_start_experiment


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_execute_result(row: dict[str, Any] | None) -> MagicMock:
    """Build a SQLAlchemy CursorResult mock whose .mappings().first() returns row."""
    result = MagicMock()
    result.mappings.return_value.first.return_value = row
    return result


def _dep_row(dep_id: uuid.UUID, gen_id: uuid.UUID) -> dict[str, Any]:
    now = datetime.now(tz=timezone.utc)
    return {
        "id": dep_id,
        "generation_id": gen_id,
        "status": "canary",
        "traffic_split": '{"baseline": 0.9, "variant": 0.1}',
        "error_count": 0,
        "total_calls": 0,
        "created_at": now,
        "updated_at": now,
    }


# ── Return value shape ────────────────────────────────────────────────────────


async def test_orchestrator_returns_deployment_with_key() -> None:
    """deploy_and_start_experiment returns (DeploymentWithKey, UUID)."""
    db = AsyncMock()
    generation_id = uuid.uuid4()
    dep_id = uuid.uuid4()
    exp_id = uuid.uuid4()

    db.execute = AsyncMock(
        side_effect=[
            _make_execute_result(_dep_row(dep_id, generation_id)),
            _make_execute_result({"id": exp_id}),
        ]
    )

    result = await deploy_and_start_experiment(db, generation_id)

    deployment, returned_exp_id = result
    assert isinstance(deployment, DeploymentWithKey)
    assert isinstance(returned_exp_id, uuid.UUID)
    assert str(returned_exp_id) == str(exp_id)
    assert str(deployment.generation_id) == str(generation_id)
    assert deployment.status == "canary"
    # api_key is a non-empty string returned to the caller
    assert isinstance(deployment.api_key, str)
    assert len(deployment.api_key) > 0


# ── API key uniqueness ────────────────────────────────────────────────────────


async def test_orchestrator_generates_unique_api_key() -> None:
    """Two separate calls must return different raw API keys."""
    generation_id = uuid.uuid4()
    dep_id_1 = uuid.uuid4()
    dep_id_2 = uuid.uuid4()
    exp_id = uuid.uuid4()

    async def _make_db(dep_id: uuid.UUID) -> AsyncMock:
        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                _make_execute_result(_dep_row(dep_id, generation_id)),
                _make_execute_result({"id": exp_id}),
            ]
        )
        return db

    db1 = await _make_db(dep_id_1)
    db2 = await _make_db(dep_id_2)

    deployment1, _ = await deploy_and_start_experiment(db1, generation_id)
    deployment2, _ = await deploy_and_start_experiment(db2, generation_id)

    assert deployment1.api_key != deployment2.api_key, (
        "Each call must generate a fresh secrets.token_urlsafe token"
    )


# ── API key hashing ───────────────────────────────────────────────────────────


async def test_orchestrator_api_key_is_not_stored_raw() -> None:
    """The value passed to DB INSERT must be the sha256 hash, not the raw key."""
    db = AsyncMock()
    generation_id = uuid.uuid4()
    dep_id = uuid.uuid4()
    exp_id = uuid.uuid4()

    captured_params: list[dict] = []

    async def _capture_execute(stmt, params=None, **kwargs):
        if params:
            captured_params.append(dict(params))
        return _make_execute_result(
            _dep_row(dep_id, generation_id)
            if len(captured_params) <= 1
            else {"id": exp_id}
        )

    db.execute = _capture_execute

    deployment, _ = await deploy_and_start_experiment(db, generation_id)

    raw_key = deployment.api_key
    expected_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    # The first INSERT (deployment) must contain key_hash, not the raw token
    dep_insert_params = captured_params[0]
    assert dep_insert_params.get("key_hash") == expected_hash, (
        "DB must store sha256(api_key), not the raw token"
    )
    assert dep_insert_params.get("key_hash") != raw_key, (
        "Raw API key must never appear in the INSERT parameters"
    )


# ── Traffic split ─────────────────────────────────────────────────────────────


async def test_orchestrator_respects_variant_fraction() -> None:
    """compute_traffic_split is called with the variant_fraction argument."""
    db = AsyncMock()
    generation_id = uuid.uuid4()
    dep_id = uuid.uuid4()
    exp_id = uuid.uuid4()

    db.execute = AsyncMock(
        side_effect=[
            _make_execute_result(_dep_row(dep_id, generation_id)),
            _make_execute_result({"id": exp_id}),
        ]
    )

    with patch(
        "src.loop.deploy.orchestrator.compute_traffic_split",
        wraps=lambda f: {"baseline": round(1.0 - f, 10), "variant": round(f, 10)},
    ) as mock_split:
        await deploy_and_start_experiment(db, generation_id, variant_fraction=0.25)

    mock_split.assert_called_once_with(0.25)


async def test_orchestrator_default_variant_fraction_is_10_percent() -> None:
    """Default variant_fraction=0.10 routes 10% to the variant."""
    db = AsyncMock()
    generation_id = uuid.uuid4()
    dep_id = uuid.uuid4()
    exp_id = uuid.uuid4()

    db.execute = AsyncMock(
        side_effect=[
            _make_execute_result(_dep_row(dep_id, generation_id)),
            _make_execute_result({"id": exp_id}),
        ]
    )

    with patch(
        "src.loop.deploy.orchestrator.compute_traffic_split",
        wraps=lambda f: {"baseline": round(1.0 - f, 10), "variant": round(f, 10)},
    ) as mock_split:
        await deploy_and_start_experiment(db, generation_id)  # no explicit fraction

    mock_split.assert_called_once_with(0.10)


# ── No commit ─────────────────────────────────────────────────────────────────


async def test_orchestrator_does_not_commit() -> None:
    """The orchestrator never calls db.commit() — caller owns the transaction."""
    db = AsyncMock()
    generation_id = uuid.uuid4()
    dep_id = uuid.uuid4()
    exp_id = uuid.uuid4()

    db.execute = AsyncMock(
        side_effect=[
            _make_execute_result(_dep_row(dep_id, generation_id)),
            _make_execute_result({"id": exp_id}),
        ]
    )

    await deploy_and_start_experiment(db, generation_id)

    db.commit.assert_not_awaited()
