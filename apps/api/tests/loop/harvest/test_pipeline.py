"""Unit tests for loop/harvest/pipeline.py — harvest_source error paths."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import httpx
import pytest


@pytest.mark.asyncio
async def test_harvest_source_crawl_error_marks_source_error():
    """CrawlError from fetch_and_extract → mark_source_error called, returns 0."""
    from src.loop.harvest.crawler import CrawlError
    from src.loop.harvest.pipeline import harvest_source

    db = AsyncMock()
    source_id = uuid.uuid4()
    inference_id = uuid.uuid4()

    with patch("src.loop.harvest.pipeline.mark_source_crawling", new=AsyncMock()), \
         patch(
             "src.loop.harvest.pipeline.fetch_and_extract",
             side_effect=CrawlError("network", "connection refused"),
         ), \
         patch("src.loop.harvest.pipeline.mark_source_error", new=AsyncMock()) as mock_err:

        result = await harvest_source(db, source_id, "https://example.com/", inference_id)

    assert result == 0
    mock_err.assert_awaited_once()


@pytest.mark.asyncio
async def test_harvest_source_empty_text_marks_error():
    """Empty text after extraction → mark_source_error with 'empty content' message."""
    from src.loop.harvest.pipeline import harvest_source

    db = AsyncMock()
    source_id = uuid.uuid4()
    inference_id = uuid.uuid4()

    with patch("src.loop.harvest.pipeline.mark_source_crawling", new=AsyncMock()), \
         patch("src.loop.harvest.pipeline.fetch_and_extract", new=AsyncMock(return_value="")), \
         patch("src.loop.harvest.pipeline.mark_source_error", new=AsyncMock()) as mock_err:

        result = await harvest_source(db, source_id, "https://example.com/", inference_id)

    assert result == 0
    mock_err.assert_awaited_once_with(db, source_id, "empty content after extraction")


@pytest.mark.asyncio
async def test_harvest_source_no_chunks_marks_error():
    """No chunks after split → mark_source_error with 'no chunks' message."""
    from src.loop.harvest.pipeline import harvest_source

    db = AsyncMock()
    source_id = uuid.uuid4()
    inference_id = uuid.uuid4()

    with patch("src.loop.harvest.pipeline.mark_source_crawling", new=AsyncMock()), \
         patch("src.loop.harvest.pipeline.fetch_and_extract", new=AsyncMock(return_value="some text")), \
         patch("src.loop.harvest.pipeline.recursive_split", return_value=[]), \
         patch("src.loop.harvest.pipeline.mark_source_error", new=AsyncMock()) as mock_err:

        result = await harvest_source(db, source_id, "https://example.com/", inference_id)

    assert result == 0
    mock_err.assert_awaited_once()
    assert "no chunks" in mock_err.await_args[0][2]


@pytest.mark.asyncio
async def test_harvest_source_embedding_runtime_error_marks_error():
    """RuntimeError from embed_texts → mark_source_error called, returns 0 (covers line 56)."""
    from src.loop.harvest.pipeline import harvest_source

    db = AsyncMock()
    source_id = uuid.uuid4()
    inference_id = uuid.uuid4()

    with patch("src.loop.harvest.pipeline.mark_source_crawling", new=AsyncMock()), \
         patch("src.loop.harvest.pipeline.fetch_and_extract", new=AsyncMock(return_value="some text")), \
         patch("src.loop.harvest.pipeline.recursive_split", return_value=["chunk1", "chunk2"]), \
         patch("src.loop.harvest.pipeline.embed_texts", side_effect=RuntimeError("Voyage API down")), \
         patch("src.loop.harvest.pipeline.mark_source_error", new=AsyncMock()) as mock_err:

        result = await harvest_source(db, source_id, "https://example.com/", inference_id)

    assert result == 0
    mock_err.assert_awaited_once()
    assert "embedding failed" in mock_err.await_args[0][2]


@pytest.mark.asyncio
async def test_harvest_source_embedding_http_error_marks_error():
    """httpx.HTTPStatusError from embed_texts → mark_source_error called."""
    from src.loop.harvest.pipeline import harvest_source

    db = AsyncMock()
    source_id = uuid.uuid4()
    inference_id = uuid.uuid4()
    http_err = httpx.HTTPStatusError(
        "429 Too Many Requests",
        request=httpx.Request("POST", "https://api.voyageai.com/"),
        response=httpx.Response(429),
    )

    with patch("src.loop.harvest.pipeline.mark_source_crawling", new=AsyncMock()), \
         patch("src.loop.harvest.pipeline.fetch_and_extract", new=AsyncMock(return_value="some text")), \
         patch("src.loop.harvest.pipeline.recursive_split", return_value=["chunk1"]), \
         patch("src.loop.harvest.pipeline.embed_texts", side_effect=http_err), \
         patch("src.loop.harvest.pipeline.mark_source_error", new=AsyncMock()) as mock_err:

        result = await harvest_source(db, source_id, "https://example.com/", inference_id)

    assert result == 0
    mock_err.assert_awaited_once()
