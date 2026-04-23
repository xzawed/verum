"""Unit tests for src/worker/chain.py — enqueue_next."""
from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, call

import pytest

from src.worker.chain import enqueue_next


async def test_enqueue_next_calls_execute_once(mock_db: AsyncMock) -> None:
    owner = uuid.uuid4()
    await enqueue_next(
        mock_db,
        kind="analyze",
        payload={"repo_url": "https://github.com/x/y"},
        owner_user_id=owner,
    )
    mock_db.execute.assert_awaited_once()


async def test_enqueue_next_does_not_commit(mock_db: AsyncMock) -> None:
    owner = uuid.uuid4()
    await enqueue_next(
        mock_db,
        kind="infer",
        payload={"analysis_id": str(uuid.uuid4())},
        owner_user_id=owner,
    )
    mock_db.commit.assert_not_awaited()


async def test_enqueue_next_different_kinds(mock_db: AsyncMock) -> None:
    owner = uuid.uuid4()
    for kind in ("analyze", "infer", "harvest", "generate", "deploy", "judge", "evolve"):
        db = AsyncMock()
        db.execute = AsyncMock()
        db.commit = AsyncMock()
        await enqueue_next(
            db,
            kind=kind,
            payload={"id": str(uuid.uuid4())},
            owner_user_id=owner,
        )
        db.execute.assert_awaited_once()
        db.commit.assert_not_awaited()


async def test_enqueue_next_payload_is_json_serialized(mock_db: AsyncMock) -> None:
    owner = uuid.uuid4()
    payload = {"repo_url": "https://github.com/x/y", "branch": "main"}
    await enqueue_next(
        mock_db,
        kind="analyze",
        payload=payload,
        owner_user_id=owner,
    )
    # Extract the params dict passed to execute
    _sql, params = mock_db.execute.call_args[0]
    serialized = params["p"]
    # Must be valid JSON that round-trips correctly
    assert json.loads(serialized) == payload


async def test_enqueue_next_owner_user_id_as_string(mock_db: AsyncMock) -> None:
    owner = uuid.UUID("12345678-1234-5678-1234-567812345678")
    await enqueue_next(
        mock_db,
        kind="analyze",
        payload={},
        owner_user_id=owner,
    )
    _sql, params = mock_db.execute.call_args[0]
    assert params["u"] == "12345678-1234-5678-1234-567812345678"


async def test_enqueue_next_kind_passed_correctly(mock_db: AsyncMock) -> None:
    owner = uuid.uuid4()
    await enqueue_next(
        mock_db,
        kind="harvest",
        payload={},
        owner_user_id=owner,
    )
    _sql, params = mock_db.execute.call_args[0]
    assert params["k"] == "harvest"
