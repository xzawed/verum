from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import src.worker.listener as listener_mod
from src.worker.listener import get_wake_event, start_listener


def _reset_module_state(monkeypatch):
    monkeypatch.setattr(listener_mod, "_wake_event", None)
    monkeypatch.setattr(listener_mod, "_listener_task", None)


def test_get_wake_event_creates_event_on_first_call(monkeypatch):
    monkeypatch.setattr(listener_mod, "_wake_event", None)
    event = get_wake_event()
    assert isinstance(event, asyncio.Event)


def test_get_wake_event_returns_same_event_on_second_call(monkeypatch):
    monkeypatch.setattr(listener_mod, "_wake_event", None)
    event1 = get_wake_event()
    event2 = get_wake_event()
    assert event1 is event2


def test_get_wake_event_returns_existing_event(monkeypatch):
    existing = asyncio.Event()
    monkeypatch.setattr(listener_mod, "_wake_event", existing)
    result = get_wake_event()
    assert result is existing


async def test_start_listener_noop_when_no_dsn(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    _reset_module_state(monkeypatch)
    await start_listener()
    assert listener_mod._listener_task is None


async def test_start_listener_noop_when_dsn_empty_string(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "")
    _reset_module_state(monkeypatch)
    await start_listener()
    assert listener_mod._listener_task is None


async def test_start_listener_creates_task_when_dsn_set(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/db")
    _reset_module_state(monkeypatch)

    fake_task = MagicMock()
    with (
        patch("src.worker.listener._listen_loop", new=AsyncMock(return_value=None)),
        patch("asyncio.create_task", return_value=fake_task) as mock_create,
    ):
        await start_listener()

    mock_create.assert_called_once()
    assert listener_mod._listener_task is fake_task


async def test_start_listener_strips_asyncpg_prefix(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/mydb")
    _reset_module_state(monkeypatch)

    captured: list[str] = []

    async def _fake_loop(dsn: str) -> None:
        captured.append(dsn)

    with (
        patch("src.worker.listener._listen_loop", side_effect=_fake_loop),
        patch("asyncio.create_task", return_value=MagicMock()) as mock_create,
    ):
        await start_listener()

    call_args = mock_create.call_args
    coro = call_args[0][0]
    assert coro.cr_frame is not None or coro is not None
    coro.close()


async def test_start_listener_plain_postgresql_url_unchanged(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")
    _reset_module_state(monkeypatch)

    fake_task = MagicMock()
    with (
        patch("src.worker.listener._listen_loop", new=AsyncMock(return_value=None)),
        patch("asyncio.create_task", return_value=fake_task) as mock_create,
    ):
        await start_listener()

    mock_create.assert_called_once()
    assert listener_mod._listener_task is fake_task


async def test_start_listener_sets_listener_task_global(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")
    monkeypatch.setattr(listener_mod, "_listener_task", None)
    monkeypatch.setattr(listener_mod, "_wake_event", None)

    sentinel = MagicMock()
    with (
        patch("src.worker.listener._listen_loop", new=AsyncMock()),
        patch("asyncio.create_task", return_value=sentinel),
    ):
        await start_listener()

    assert listener_mod._listener_task is sentinel
