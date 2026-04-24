"""Unit tests for the GENERATE stage repository."""
from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from src.loop.generate.models import EvalPair, GenerateResult, PromptVariant, RagConfig


def _make_result(inference_id: uuid.UUID, **overrides) -> GenerateResult:
    defaults = dict(
        inference_id=inference_id,
        prompt_variants=[
            PromptVariant(
                variant_type="original",
                content="Hello {name}",
                variables=["name"],
            )
        ],
        rag_config=RagConfig(),
        eval_pairs=[
            EvalPair(
                query="What is tarot?",
                expected_answer="A divination system using 78 cards.",
                context_needed=True,
            )
        ],
    )
    defaults.update(overrides)
    return GenerateResult(**defaults)


# ---------------------------------------------------------------------------
# Test 1 — save_generate_result: non-existent generation_id must raise
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_save_generate_result_missing_row_raises() -> None:
    """save_generate_result raises ValueError for a generation_id that was never inserted."""
    from src.loop.generate.repository import save_generate_result

    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result_mock)

    ghost_id = uuid.uuid4()
    result = _make_result(inference_id=uuid.uuid4())

    with pytest.raises(ValueError, match=str(ghost_id)):
        await save_generate_result(db, ghost_id, result)


# ---------------------------------------------------------------------------
# Test 2 — mark_generate_error: idempotency on double-call
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mark_generate_error_idempotent() -> None:
    """Calling mark_generate_error twice on the same generation_id must not raise."""
    from src.loop.generate.repository import mark_generate_error

    gen_id = uuid.uuid4()

    mock_row = MagicMock()
    mock_row.status = "pending"
    mock_row.error = None

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = mock_row

    db = AsyncMock()
    db.execute = AsyncMock(return_value=result_mock)

    await mark_generate_error(db, gen_id, "first error")
    assert mock_row.status == "error"
    assert mock_row.error == "first error"

    # Second call with same row still returned — simulates idempotent behavior
    await mark_generate_error(db, gen_id, "second error")
    assert mock_row.error == "second error"
    assert db.commit.await_count == 2


# ---------------------------------------------------------------------------
# Test 3 — get_generation_summary: no matching row returns None
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_generation_summary_no_row_returns_none() -> None:
    """get_generation_summary returns None when no generation exists for the given inference."""
    from src.loop.generate.repository import get_generation_summary

    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.mappings.return_value.first.return_value = None
    db.execute = AsyncMock(return_value=result_mock)

    summary = await get_generation_summary(db, uuid.uuid4())

    assert summary is None


# ---------------------------------------------------------------------------
# Test 4 — save_generate_result: JSON special chars in variables field
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_save_generate_result_special_chars_in_variables() -> None:
    """Variables list with quotes, backslashes, and unicode must not raise on INSERT."""
    from src.loop.generate.repository import save_generate_result

    gen_id = uuid.uuid4()
    inference_id = uuid.uuid4()

    mock_gen = MagicMock()
    mock_gen.id = gen_id
    mock_gen.status = "pending"

    select_result = MagicMock()
    select_result.scalar_one_or_none.return_value = mock_gen

    insert_result = MagicMock()

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[select_result, insert_result, insert_result, insert_result])

    tricky_vars = ['name"quoted"', "back\\slash", "unicode_한글", "emoji_🔮"]
    result = _make_result(
        inference_id=inference_id,
        prompt_variants=[
            PromptVariant(
                variant_type="original",
                content="Hello {name}",
                variables=tricky_vars,
            )
        ],
    )

    await save_generate_result(db, gen_id, result)

    insert_call = db.execute.call_args_list[1]
    params = insert_call.args[1]
    round_tripped = json.loads(params["vars"])
    assert round_tripped == tricky_vars


# ---------------------------------------------------------------------------
# Test 5 — concurrent duplicate call: documents known race condition
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_save_generate_result_concurrent_calls_no_double_insert() -> None:
    """Two concurrent save calls for the same generation_id must complete without error.

    rag_configs INSERT uses ON CONFLICT (generation_id) DO NOTHING so the second
    call silently skips the duplicate instead of raising IntegrityError.
    Migration 0007_rag_configs_unique adds the UNIQUE(generation_id) constraint.
    """
    import asyncio

    from src.loop.generate.repository import save_generate_result

    gen_id = uuid.uuid4()
    result = _make_result(inference_id=uuid.uuid4())

    def _make_mock_db() -> AsyncMock:
        row = MagicMock()
        row.status = "pending"
        row.generated_at = None
        row.metric_profile = None
        sel = MagicMock()
        sel.scalar_one_or_none.return_value = row
        db = AsyncMock()
        db.execute = AsyncMock(return_value=sel)
        return db

    db1, db2 = _make_mock_db(), _make_mock_db()

    # Both must complete without raising
    await asyncio.gather(
        save_generate_result(db1, gen_id, result),
        save_generate_result(db2, gen_id, result),
    )

    # Both sessions committed (each does its own db.commit())
    db1.commit.assert_called_once()
    db2.commit.assert_called_once()

    # The rag_configs INSERT must include ON CONFLICT DO NOTHING
    for db in (db1, db2):
        rag_sql = next(
            (str(c.args[0]) for c in db.execute.call_args_list
             if c.args and "rag_configs" in str(c.args[0])),
            None,
        )
        assert rag_sql is not None, "rag_configs INSERT not found in execute calls"
        assert "ON CONFLICT" in rag_sql, "rag_configs INSERT missing ON CONFLICT DO NOTHING"
