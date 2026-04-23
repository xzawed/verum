"""Unit tests for src/loop/llm_client.py — _get_client and call_claude."""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_text_block(text: str) -> MagicMock:
    block = MagicMock()
    block.text = text
    return block


def _make_non_text_block() -> MagicMock:
    block = MagicMock(spec=[])  # no 'text' attribute
    return block


def _make_response(*blocks: MagicMock) -> MagicMock:
    response = MagicMock()
    response.content = list(blocks)
    return response


class TestGetClient:
    def test_raises_without_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        from src.loop import llm_client
        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
            llm_client._get_client()

    def test_returns_client_when_key_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
        with patch("anthropic.AsyncAnthropic") as MockClient:
            MockClient.return_value = MagicMock()
            from src.loop import llm_client
            client = llm_client._get_client()
            assert client is not None


class TestCallClaude:
    async def test_returns_text_from_first_text_block(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        mock_create = AsyncMock(
            return_value=_make_response(_make_text_block("Hello world"))
        )
        mock_client = MagicMock()
        mock_client.messages.create = mock_create

        with patch("src.loop.llm_client._get_client", return_value=mock_client):
            from src.loop.llm_client import call_claude
            result = await call_claude("claude-sonnet-4-6", 100, "Hi")

        assert result == "Hello world"

    async def test_returns_empty_when_no_text_block(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        mock_create = AsyncMock(
            return_value=_make_response(_make_non_text_block())
        )
        mock_client = MagicMock()
        mock_client.messages.create = mock_create

        with patch("src.loop.llm_client._get_client", return_value=mock_client):
            from src.loop.llm_client import call_claude
            result = await call_claude("claude-sonnet-4-6", 100, "Hi")

        assert result == ""

    async def test_omits_system_kwarg_when_empty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        mock_create = AsyncMock(
            return_value=_make_response(_make_text_block("ok"))
        )
        mock_client = MagicMock()
        mock_client.messages.create = mock_create

        with patch("src.loop.llm_client._get_client", return_value=mock_client):
            from src.loop.llm_client import call_claude
            await call_claude("claude-sonnet-4-6", 100, "Hi", system="")

        call_kwargs = mock_create.call_args[1]
        assert "system" not in call_kwargs

    async def test_includes_system_kwarg_when_provided(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        mock_create = AsyncMock(
            return_value=_make_response(_make_text_block("ok"))
        )
        mock_client = MagicMock()
        mock_client.messages.create = mock_create

        with patch("src.loop.llm_client._get_client", return_value=mock_client):
            from src.loop.llm_client import call_claude
            await call_claude("claude-sonnet-4-6", 100, "Hi", system="You are helpful.")

        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["system"] == "You are helpful."

    async def test_uses_first_text_block_from_multiple(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        mock_create = AsyncMock(
            return_value=_make_response(
                _make_non_text_block(),
                _make_text_block("second block"),
                _make_text_block("third block"),
            )
        )
        mock_client = MagicMock()
        mock_client.messages.create = mock_create

        with patch("src.loop.llm_client._get_client", return_value=mock_client):
            from src.loop.llm_client import call_claude
            result = await call_claude("claude-sonnet-4-6", 100, "Hi")

        assert result == "second block"

    async def test_passes_model_and_max_tokens(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        mock_create = AsyncMock(
            return_value=_make_response(_make_text_block("ok"))
        )
        mock_client = MagicMock()
        mock_client.messages.create = mock_create

        with patch("src.loop.llm_client._get_client", return_value=mock_client):
            from src.loop.llm_client import call_claude
            await call_claude("claude-opus-4", 512, "prompt text")

        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["model"] == "claude-opus-4"
        assert call_kwargs["max_tokens"] == 512
        assert call_kwargs["messages"] == [{"role": "user", "content": "prompt text"}]
