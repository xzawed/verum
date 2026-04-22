"""Tests that harvest_source routes to the correct chunker."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.loop.harvest.pipeline import harvest_source


@pytest.fixture()
def mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    return db


@pytest.mark.asyncio
async def test_default_strategy_calls_recursive_split(mock_db):
    """harvest_source without explicit strategy uses recursive_split."""
    source_id = uuid.uuid4()
    inference_id = uuid.uuid4()

    with (
        patch("src.loop.harvest.pipeline.mark_source_crawling", new_callable=AsyncMock),
        patch("src.loop.harvest.pipeline.fetch_and_extract", new_callable=AsyncMock, return_value="some text " * 100),
        patch("src.loop.harvest.pipeline.recursive_split", return_value=["chunk1", "chunk2"]) as mock_rec,
        patch("src.loop.harvest.pipeline.semantic_split", return_value=["sem1"]) as mock_sem,
        patch("src.loop.harvest.pipeline.embed_texts", new_callable=AsyncMock, return_value=[[0.1] * 3, [0.2] * 3]),
        patch("src.loop.harvest.pipeline.save_chunks", new_callable=AsyncMock, return_value=2),
        patch("src.loop.harvest.pipeline.mark_source_done", new_callable=AsyncMock),
    ):
        await harvest_source(mock_db, source_id, "https://example.com", inference_id)
        mock_rec.assert_called_once()
        mock_sem.assert_not_called()


@pytest.mark.asyncio
async def test_semantic_strategy_calls_semantic_split(mock_db):
    """harvest_source with chunking_strategy='semantic' uses semantic_split."""
    source_id = uuid.uuid4()
    inference_id = uuid.uuid4()

    with (
        patch("src.loop.harvest.pipeline.mark_source_crawling", new_callable=AsyncMock),
        patch("src.loop.harvest.pipeline.fetch_and_extract", new_callable=AsyncMock, return_value="some text " * 100),
        patch("src.loop.harvest.pipeline.recursive_split", return_value=["rec1"]) as mock_rec,
        patch("src.loop.harvest.pipeline.semantic_split", return_value=["sem1", "sem2"]) as mock_sem,
        patch("src.loop.harvest.pipeline.embed_texts", new_callable=AsyncMock, return_value=[[0.1] * 3, [0.2] * 3]),
        patch("src.loop.harvest.pipeline.save_chunks", new_callable=AsyncMock, return_value=2),
        patch("src.loop.harvest.pipeline.mark_source_done", new_callable=AsyncMock),
    ):
        await harvest_source(
            mock_db, source_id, "https://example.com", inference_id,
            chunking_strategy="semantic",
        )
        mock_sem.assert_called_once()
        mock_rec.assert_not_called()


@pytest.mark.asyncio
async def test_unknown_strategy_falls_back_to_recursive(mock_db):
    """Unknown strategy names fall back to recursive_split."""
    source_id = uuid.uuid4()
    inference_id = uuid.uuid4()

    with (
        patch("src.loop.harvest.pipeline.mark_source_crawling", new_callable=AsyncMock),
        patch("src.loop.harvest.pipeline.fetch_and_extract", new_callable=AsyncMock, return_value="some text " * 100),
        patch("src.loop.harvest.pipeline.recursive_split", return_value=["r1"]) as mock_rec,
        patch("src.loop.harvest.pipeline.semantic_split", return_value=["s1"]) as mock_sem,
        patch("src.loop.harvest.pipeline.embed_texts", new_callable=AsyncMock, return_value=[[0.1] * 3]),
        patch("src.loop.harvest.pipeline.save_chunks", new_callable=AsyncMock, return_value=1),
        patch("src.loop.harvest.pipeline.mark_source_done", new_callable=AsyncMock),
    ):
        await harvest_source(
            mock_db, source_id, "https://example.com", inference_id,
            chunking_strategy="nonexistent_strategy",
        )
        mock_rec.assert_called_once()
        mock_sem.assert_not_called()
