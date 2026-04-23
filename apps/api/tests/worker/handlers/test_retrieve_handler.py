"""Unit tests for the RETRIEVE job handler."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from src.worker.handlers.retrieve import handle_retrieve


def _make_chunk_result(count: int, base_score: float = 0.9):
    return [
        {"content": f"chunk {i}", "score": base_score - i * 0.05}
        for i in range(count)
    ]


@pytest.mark.asyncio
async def test_handle_retrieve_hybrid_merges_and_dedupes() -> None:
    """Hybrid mode merges vector + text results and deduplicates by content."""
    db = AsyncMock()
    inference_id = uuid.uuid4()

    vector_chunks = [
        {"content": "shared content", "score": 0.95},
        {"content": "vector only", "score": 0.85},
    ]
    text_chunks = [
        {"content": "shared content", "score": 0.80},
        {"content": "text only", "score": 0.75},
    ]

    with patch("src.worker.handlers.retrieve.embed_texts", new=AsyncMock(return_value=[[0.1] * 1536])), \
         patch("src.worker.handlers.retrieve.vector_search", new=AsyncMock(return_value=vector_chunks)), \
         patch("src.worker.handlers.retrieve.text_search", new=AsyncMock(return_value=text_chunks)):

        result = await handle_retrieve(
            db=db,
            owner_user_id=uuid.uuid4(),
            payload={
                "inference_id": str(inference_id),
                "query": "tarot meaning",
                "hybrid": True,
                "top_k": 5,
            },
        )

    contents = [r["content"] for r in result["results"]]
    assert "shared content" in contents
    assert "vector only" in contents
    assert "text only" in contents
    assert contents.count("shared content") == 1
    assert result["total_chunks"] == 3


@pytest.mark.asyncio
async def test_handle_retrieve_non_hybrid_uses_vector_only() -> None:
    """Non-hybrid mode skips text_search and uses vector results only."""
    db = AsyncMock()

    vector_chunks = _make_chunk_result(3)

    with patch("src.worker.handlers.retrieve.embed_texts", new=AsyncMock(return_value=[[0.1] * 1536])), \
         patch("src.worker.handlers.retrieve.vector_search", new=AsyncMock(return_value=vector_chunks)) as mock_vs, \
         patch("src.worker.handlers.retrieve.text_search", new=AsyncMock()) as mock_ts:

        result = await handle_retrieve(
            db=db,
            owner_user_id=uuid.uuid4(),
            payload={
                "inference_id": str(uuid.uuid4()),
                "query": "test",
                "hybrid": False,
                "top_k": 3,
            },
        )

    mock_vs.assert_awaited_once()
    mock_ts.assert_not_awaited()
    assert result["total_chunks"] == 3


@pytest.mark.asyncio
async def test_handle_retrieve_defaults_to_hybrid_top5() -> None:
    """hybrid and top_k default to True and 5 when not in payload."""
    db = AsyncMock()

    with patch("src.worker.handlers.retrieve.embed_texts", new=AsyncMock(return_value=[[0.1]])), \
         patch("src.worker.handlers.retrieve.vector_search", new=AsyncMock(return_value=[])), \
         patch("src.worker.handlers.retrieve.text_search", new=AsyncMock(return_value=[])) as mock_ts:

        await handle_retrieve(
            db=db,
            owner_user_id=uuid.uuid4(),
            payload={
                "inference_id": str(uuid.uuid4()),
                "query": "hello",
            },
        )

    mock_ts.assert_awaited_once()
    _, _, kwargs = mock_ts.await_args.args[0], mock_ts.await_args.args[1], mock_ts.await_args.kwargs
    assert kwargs.get("top_k") == 5
