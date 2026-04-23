"""Tests for HARVEST stage repository I/O."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.loop.harvest.repository import vector_search


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
