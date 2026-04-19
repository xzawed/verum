"""Tests for HARVEST stage Voyage AI embedder."""
from __future__ import annotations

import json

import httpx
import pytest
import respx

from src.loop.harvest.embedder import embed_texts

_FAKE_EMBED_URL = "https://api.voyageai.com/v1/embeddings"


def _fake_response(count: int, dim: int = 1024) -> dict:  # type: ignore[type-arg]
    return {
        "data": [{"embedding": [0.1] * dim, "index": i} for i in range(count)],
        "model": "voyage-3.5",
        "usage": {"total_tokens": count * 5},
    }


async def test_raises_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VOYAGE_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="VOYAGE_API_KEY"):
        await embed_texts(["hello"])


async def test_returns_1024_dim_vectors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VOYAGE_API_KEY", "test-key")

    with respx.mock:
        respx.post(_FAKE_EMBED_URL).mock(
            return_value=httpx.Response(200, json=_fake_response(2))
        )
        result = await embed_texts(["hello", "world"])

    assert len(result) == 2
    assert len(result[0]) == 1024
    assert len(result[1]) == 1024


async def test_passes_document_input_type_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VOYAGE_API_KEY", "test-key")
    captured: dict[str, object] = {}

    with respx.mock:
        def capture(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json=_fake_response(1))

        respx.post(_FAKE_EMBED_URL).mock(side_effect=capture)
        await embed_texts(["some chunk"])

    assert captured["body"]["input_type"] == "document"  # type: ignore[index]


async def test_passes_query_input_type_when_specified(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VOYAGE_API_KEY", "test-key")
    captured: dict[str, object] = {}

    with respx.mock:
        def capture(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json=_fake_response(1))

        respx.post(_FAKE_EMBED_URL).mock(side_effect=capture)
        await embed_texts(["what is tarot?"], input_type="query")

    assert captured["body"]["input_type"] == "query"  # type: ignore[index]


async def test_raises_on_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VOYAGE_API_KEY", "test-key")

    with respx.mock:
        respx.post(_FAKE_EMBED_URL).mock(
            return_value=httpx.Response(401, json={"detail": "invalid key"})
        )
        with pytest.raises(httpx.HTTPStatusError):
            await embed_texts(["hello"])
