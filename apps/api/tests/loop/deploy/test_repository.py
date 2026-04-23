"""Unit tests for the DEPLOY stage repository (src.loop.deploy.repository)."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest


_NOW = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# create_deployment
# ---------------------------------------------------------------------------

async def test_create_deployment_returns_deployment_with_key(mock_db: AsyncMock) -> None:
    """create_deployment returns a DeploymentWithKey with a non-empty api_key."""
    from src.loop.deploy.repository import create_deployment

    dep_id = uuid.uuid4()
    gen_id = uuid.uuid4()
    row = {
        "id": str(dep_id),
        "generation_id": str(gen_id),
        "status": "canary",
        "traffic_split": json.dumps({"baseline": 0.9, "variant": 0.1}),
        "error_count": 0,
        "total_calls": 0,
        "created_at": _NOW,
        "updated_at": _NOW,
    }
    result_mock = MagicMock()
    result_mock.mappings.return_value.first.return_value = row
    mock_db.execute = AsyncMock(return_value=result_mock)

    dep_with_key = await create_deployment(mock_db, gen_id, variant_fraction=0.10)

    assert dep_with_key.api_key != ""
    assert len(dep_with_key.api_key) > 16
    assert dep_with_key.deployment_id == dep_id
    mock_db.commit.assert_awaited_once()


async def test_create_deployment_stores_hash_not_raw_key(mock_db: AsyncMock) -> None:
    """The raw API key must not appear in the SQL params — only its SHA-256 hash."""
    import hashlib

    from src.loop.deploy.repository import create_deployment

    gen_id = uuid.uuid4()
    dep_id = uuid.uuid4()
    row = {
        "id": str(dep_id),
        "generation_id": str(gen_id),
        "status": "canary",
        "traffic_split": json.dumps({"baseline": 0.9, "variant": 0.1}),
        "error_count": 0,
        "total_calls": 0,
        "created_at": _NOW,
        "updated_at": _NOW,
    }
    result_mock = MagicMock()
    result_mock.mappings.return_value.first.return_value = row
    mock_db.execute = AsyncMock(return_value=result_mock)

    dep_with_key = await create_deployment(mock_db, gen_id)

    raw_key = dep_with_key.api_key
    params = mock_db.execute.call_args.args[1]

    expected_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    assert params["key_hash"] == expected_hash
    assert raw_key not in str(params), "Raw key must not appear in params"


async def test_create_deployment_uses_correct_variant_fraction(mock_db: AsyncMock) -> None:
    """Traffic split in the INSERT reflects the given variant_fraction."""
    from src.loop.deploy.repository import create_deployment

    gen_id = uuid.uuid4()
    dep_id = uuid.uuid4()
    row = {
        "id": str(dep_id),
        "generation_id": str(gen_id),
        "status": "canary",
        "traffic_split": json.dumps({"baseline": 0.7, "variant": 0.3}),
        "error_count": 0,
        "total_calls": 0,
        "created_at": _NOW,
        "updated_at": _NOW,
    }
    result_mock = MagicMock()
    result_mock.mappings.return_value.first.return_value = row
    mock_db.execute = AsyncMock(return_value=result_mock)

    await create_deployment(mock_db, gen_id, variant_fraction=0.30)

    params = mock_db.execute.call_args.args[1]
    split = json.loads(params["split"])
    assert split["baseline"] == pytest.approx(0.70, abs=0.01)
    assert split["variant"] == pytest.approx(0.30, abs=0.01)


async def test_create_deployment_raises_when_insert_returns_no_row(
    mock_db: AsyncMock,
) -> None:
    """create_deployment raises RuntimeError when INSERT RETURNING yields nothing."""
    from src.loop.deploy.repository import create_deployment

    result_mock = MagicMock()
    result_mock.mappings.return_value.first.return_value = None
    mock_db.execute = AsyncMock(return_value=result_mock)

    with pytest.raises(RuntimeError, match="no row"):
        await create_deployment(mock_db, uuid.uuid4())


# ---------------------------------------------------------------------------
# get_deployment
# ---------------------------------------------------------------------------

async def test_get_deployment_returns_none_when_missing(mock_db: AsyncMock) -> None:
    """get_deployment returns None for an unknown deployment_id."""
    from src.loop.deploy.repository import get_deployment

    result_mock = MagicMock()
    result_mock.mappings.return_value.first.return_value = None
    mock_db.execute = AsyncMock(return_value=result_mock)

    dep = await get_deployment(mock_db, uuid.uuid4())
    assert dep is None


# ---------------------------------------------------------------------------
# update_traffic
# ---------------------------------------------------------------------------

async def test_update_traffic_commits_after_update(mock_db: AsyncMock) -> None:
    """update_traffic executes UPDATE and commits."""
    from src.loop.deploy.repository import update_traffic

    dep_id = uuid.uuid4()
    gen_id = uuid.uuid4()
    row = {
        "id": str(dep_id),
        "generation_id": str(gen_id),
        "status": "canary",
        "traffic_split": json.dumps({"baseline": 0.8, "variant": 0.2}),
        "error_count": 0,
        "total_calls": 0,
        "created_at": _NOW,
        "updated_at": _NOW,
    }
    result_mock = MagicMock()
    result_mock.mappings.return_value.first.return_value = row
    mock_db.execute = AsyncMock(return_value=result_mock)

    dep = await update_traffic(mock_db, dep_id, variant_fraction=0.20)

    assert dep is not None
    mock_db.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# rollback_deployment
# ---------------------------------------------------------------------------

async def test_rollback_deployment_sets_rolled_back_status(mock_db: AsyncMock) -> None:
    """rollback_deployment returns a deployment with status='rolled_back'."""
    from src.loop.deploy.repository import rollback_deployment

    dep_id = uuid.uuid4()
    gen_id = uuid.uuid4()
    row = {
        "id": str(dep_id),
        "generation_id": str(gen_id),
        "status": "rolled_back",
        "traffic_split": json.dumps({"baseline": 1.0, "variant": 0.0}),
        "error_count": 0,
        "total_calls": 0,
        "created_at": _NOW,
        "updated_at": _NOW,
    }
    result_mock = MagicMock()
    result_mock.mappings.return_value.first.return_value = row
    mock_db.execute = AsyncMock(return_value=result_mock)

    dep = await rollback_deployment(mock_db, dep_id)

    assert dep is not None
    assert dep.status == "rolled_back"
    split = dep.traffic_split
    assert split["baseline"] == pytest.approx(1.0)
    assert split["variant"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# get_variant_prompt
# ---------------------------------------------------------------------------

async def test_get_variant_prompt_returns_none_when_no_cot_variant(
    mock_db: AsyncMock,
) -> None:
    """get_variant_prompt returns None when no CoT variant exists for the deployment."""
    from src.loop.deploy.repository import get_variant_prompt

    result_mock = MagicMock()
    result_mock.mappings.return_value.first.return_value = None
    mock_db.execute = AsyncMock(return_value=result_mock)

    content = await get_variant_prompt(mock_db, uuid.uuid4())
    assert content is None
