"""Tests for HARVEST stage repository I/O."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.loop.harvest.repository import (
    count_chunks,
    get_approved_sources,
    mark_source_crawling,
    mark_source_done,
    mark_source_error,
    save_chunks,
    text_search,
    vector_search,
)


@pytest.mark.asyncio
async def test_vector_search_parameterizes_vector_correctly() -> None:
    """Verify vector_search uses bound parameters for vector, not f-string interpolation.

    This test ensures the SQL injection vulnerability via f-string interpolation is fixed.
    The vector value should be passed as a bound parameter (:vec), not embedded in the SQL text.
    """
    inference_id = uuid.uuid4()
    query_embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
    top_k = 5

    # Mock the database session
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [
        (uuid.uuid4(), "chunk content 1", 0.95),
        (uuid.uuid4(), "chunk content 2", 0.87),
    ]

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result

    # Call the function
    result = await vector_search(mock_session, inference_id, query_embedding, top_k)

    # Verify the result structure
    assert len(result) == 2
    assert all("chunk_id" in r and "content" in r and "score" in r for r in result)
    assert result[0]["score"] == pytest.approx(0.95)
    assert result[1]["score"] == pytest.approx(0.87)

    # Verify execute was called
    assert mock_session.execute.called

    # Get the SQL text that was passed to execute
    call_args = mock_session.execute.call_args
    assert call_args is not None

    sql_text = call_args[0][0]  # First positional arg is the text() object
    params = call_args[0][1]    # Second positional arg is the params dict

    # The critical security check: the vector value must NOT appear in the SQL text itself
    vec_str = "[" + ",".join(str(v) for v in query_embedding) + "]"
    sql_text_str = str(sql_text)

    # Verify the vector string is NOT interpolated into the SQL (would be a SQL injection risk)
    assert vec_str not in sql_text_str, (
        f"Vector value {vec_str} should not be in SQL text (should be bound parameter). "
        f"Found in: {sql_text_str}"
    )

    # Verify the vector is instead in the parameters dict as a bound parameter
    assert "vec" in params, "Vector should be passed as :vec bound parameter"
    assert params["vec"] == vec_str, "Bound parameter 'vec' should contain the vector string"

    # Verify other parameters are also bound
    assert "inf_id" in params, "inference_id should be passed as :inf_id bound parameter"
    assert "k" in params, "top_k should be passed as :k bound parameter"
    assert params["k"] == top_k


@pytest.mark.asyncio
async def test_vector_search_handles_empty_results() -> None:
    """Verify vector_search handles empty result set correctly."""
    inference_id = uuid.uuid4()
    query_embedding = [0.1] * 1024

    mock_result = MagicMock()
    mock_result.fetchall.return_value = []

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result

    result = await vector_search(mock_session, inference_id, query_embedding)

    assert result == []


# ---------------------------------------------------------------------------
# get_approved_sources, mark_source_*, save_chunks, count_chunks, text_search
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_approved_sources_returns_list():
    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [MagicMock(), MagicMock()]
    db.execute.return_value = result_mock

    sources = await get_approved_sources(db, uuid.uuid4())
    assert len(sources) == 2
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_mark_source_crawling_commits():
    db = AsyncMock()
    db.commit = AsyncMock()
    db.execute = AsyncMock()
    await mark_source_crawling(db, uuid.uuid4())
    db.execute.assert_awaited_once()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_mark_source_done_commits():
    db = AsyncMock()
    db.commit = AsyncMock()
    db.execute = AsyncMock()
    await mark_source_done(db, uuid.uuid4(), chunks_count=42)
    db.execute.assert_awaited_once()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_mark_source_error_delegates_to_mark_error():
    db = AsyncMock()
    with patch("src.db.error_helpers.mark_error", new=AsyncMock()) as mock_err:
        await mark_source_error(db, uuid.uuid4(), "crawl failed")
    mock_err.assert_awaited_once()


@pytest.mark.asyncio
async def test_save_chunks_empty_list_returns_zero():
    db = AsyncMock()
    db.flush = AsyncMock()
    count = await save_chunks(db, uuid.uuid4(), uuid.uuid4(), [], [])
    assert count == 0
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_save_chunks_with_content_adds_and_flushes():
    db = AsyncMock()
    db.flush = AsyncMock()
    db.execute = AsyncMock()
    db.add = MagicMock()

    texts = ["chunk A", "chunk B"]
    embeddings = [[0.1] * 1024, [0.2] * 1024]
    count = await save_chunks(db, uuid.uuid4(), uuid.uuid4(), texts, embeddings)

    assert count == 2
    assert db.add.call_count == 2
    db.flush.assert_awaited_once()
    db.execute.assert_awaited_once()  # bulk UPDATE for embeddings


@pytest.mark.asyncio
async def test_count_chunks_returns_integer():
    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.fetchone.return_value = (7,)
    db.execute.return_value = result_mock

    count = await count_chunks(db, uuid.uuid4())
    assert count == 7


@pytest.mark.asyncio
async def test_count_chunks_returns_zero_on_no_row():
    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.fetchone.return_value = None
    db.execute.return_value = result_mock

    count = await count_chunks(db, uuid.uuid4())
    assert count == 0


@pytest.mark.asyncio
async def test_text_search_returns_list():
    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.fetchall.return_value = [
        (uuid.uuid4(), "tarot content", 0.88),
    ]
    db.execute.return_value = result_mock

    results = await text_search(db, uuid.uuid4(), "tarot meaning")
    assert len(results) == 1
    assert results[0]["content"] == "tarot content"
    assert results[0]["score"] == pytest.approx(0.88)


@pytest.mark.asyncio
async def test_vector_search_respects_top_k_parameter() -> None:
    """Verify vector_search passes the top_k parameter correctly."""
    inference_id = uuid.uuid4()
    query_embedding = [0.1] * 1024
    top_k = 10

    mock_result = MagicMock()
    mock_result.fetchall.return_value = []

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result

    await vector_search(mock_session, inference_id, query_embedding, top_k=top_k)

    # Verify the parameter was passed correctly
    call_args = mock_session.execute.call_args
    params = call_args[0][1]

    assert params["k"] == top_k


@pytest.mark.asyncio
async def test_save_chunks_embedding_update_uses_no_string_interpolation() -> None:
    db = AsyncMock()
    db.flush = AsyncMock()
    db.execute = AsyncMock()
    db.add = MagicMock()

    cid = uuid.uuid4()
    emb = [0.1] * 1024
    await save_chunks(db, uuid.uuid4(), uuid.uuid4(), ["text"], [emb])

    call_args = db.execute.call_args
    sql_obj = call_args[0][0]
    param_list = call_args[0][1]

    sql_str = str(sql_obj)
    vec_str = "[" + ",".join(str(v) for v in emb) + "]"

    assert vec_str not in sql_str, "Vector must be a bound parameter, not interpolated SQL"
    assert isinstance(param_list, list) and len(param_list) == 1
    row = param_list[0]
    assert "id" in row and "vec" in row
    assert row["vec"] == vec_str
