"""Stub tests documenting expected behavior for the GENERATE stage repository.

All tests are skipped because they require a live DB fixture.
They serve as a contract spec — implement fixtures and remove the skip
markers when the DB test harness is in place (Phase 2+).
"""
from __future__ import annotations

import uuid

import pytest

from src.loop.generate.models import EvalPair, GenerateResult, PromptVariant, RagConfig

# ---------------------------------------------------------------------------
# Helper factory — builds a minimal GenerateResult without DB I/O
# ---------------------------------------------------------------------------

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

@pytest.mark.skip(reason="needs db fixture — scalar_one() should raise NoResultFound")
@pytest.mark.asyncio
async def test_save_generate_result_missing_row_raises(db_session):
    """save_generate_result called with a generation_id that was never inserted
    must propagate sqlalchemy.exc.NoResultFound (not silently succeed or insert
    orphaned child rows).

    Current implementation at line 36 uses scalar_one() which raises if the
    parent row is absent, but there is no explicit try/except — the exception
    bubbles raw to the caller.  This test documents the EXPECTED contract:
    the function should raise (or wrap) NoResultFound so callers can distinguish
    a missing-row failure from a DB connection failure.
    """
    from sqlalchemy.exc import NoResultFound
    from src.loop.generate.repository import save_generate_result

    ghost_id = uuid.uuid4()
    result = _make_result(inference_id=uuid.uuid4())

    with pytest.raises(NoResultFound):
        await save_generate_result(db_session, ghost_id, result)


# ---------------------------------------------------------------------------
# Test 2 — mark_generate_error: idempotency on double-call
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="needs db fixture — second call should overwrite, not raise")
@pytest.mark.asyncio
async def test_mark_generate_error_idempotent(db_session, inference_row):
    """Calling mark_generate_error twice on the same generation_id must not raise.

    Expected behavior: the second call overwrites status/error with new values.
    This tests that scalar_one() at line 97 still finds the row on the second
    call (status column was already 'error' from the first call).

    Current implementation has no guard — the second call will succeed because
    the row still exists.  If a future refactor adds a guard like
    'WHERE status != "error"' this test will catch the regression.
    """
    from src.loop.generate.repository import (
        create_pending_generation,
        mark_generate_error,
    )

    gen_id = uuid.uuid4()
    await create_pending_generation(db_session, inference_row.id, gen_id)

    await mark_generate_error(db_session, gen_id, "first error")
    # Second call — should NOT raise, should update the error field
    await mark_generate_error(db_session, gen_id, "second error")

    from sqlalchemy import select
    from src.db.models.generations import Generation

    row = (await db_session.execute(select(Generation).where(Generation.id == gen_id))).scalar_one()
    assert row.status == "error"
    assert row.error == "second error"


# ---------------------------------------------------------------------------
# Test 3 — get_generation_summary: no matching row returns None
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="needs db fixture — must return None, not raise")
@pytest.mark.asyncio
async def test_get_generation_summary_no_row_returns_none(db_session):
    """get_generation_summary called with an inference_id that has no linked
    generation must return None (not raise, not return an empty dict).

    Lines 119-120 use result.mappings().first() which returns None when the
    query yields no rows.  The subsequent `dict(row) if row else None` guard
    is correct — this test verifies the whole path end-to-end.
    """
    from src.loop.generate.repository import get_generation_summary

    missing_inference_id = uuid.uuid4()
    summary = await get_generation_summary(db_session, missing_inference_id)

    assert summary is None


# ---------------------------------------------------------------------------
# Test 4 — save_generate_result: JSON special chars in variables field
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="needs db fixture — JSONB round-trip with special chars")
@pytest.mark.asyncio
async def test_save_generate_result_special_chars_in_variables(db_session, inference_row):
    """Variables list containing quotes, backslashes, and unicode must round-trip
    through the JSONB column without corruption or SQL errors.

    The INSERT at lines 41-53 passes json.dumps(variant.variables) as :vars and
    casts it with ::jsonb.  PostgreSQL accepts any valid JSON in a JSONB column,
    but malformed output from json.dumps (e.g. surrogate pairs) can cause a
    DataError.  This test documents the expected round-trip guarantee.
    """
    from src.loop.generate.repository import (
        create_pending_generation,
        save_generate_result,
        get_generation_summary,
    )

    gen_id = uuid.uuid4()
    await create_pending_generation(db_session, inference_row.id, gen_id)

    tricky_vars = ['name"quoted"', "back\\slash", "unicode_한글", "emoji_🔮"]
    result = _make_result(
        inference_id=inference_row.id,
        prompt_variants=[
            PromptVariant(
                variant_type="original",
                content="Hello {name}",
                variables=tricky_vars,
            )
        ],
    )

    # Must not raise DataError or UnicodeEncodeError
    await save_generate_result(db_session, gen_id, result)

    # Verify child row was written (summary counts it)
    summary = await get_generation_summary(db_session, inference_row.id)
    assert summary is not None
    assert summary["variant_count"] == 1


# ---------------------------------------------------------------------------
# Test 5 — save_generate_result: concurrent duplicate call must not double-insert
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="needs db fixture + concurrency harness — documents race condition")
@pytest.mark.asyncio
async def test_save_generate_result_concurrent_calls_no_double_insert(db_session, inference_row):
    """Two concurrent save_generate_result calls for the same generation_id must
    not produce duplicate child rows in prompt_variants / eval_pairs.

    CURRENT STATUS — KNOWN BUG (see analysis report):
    There is NO uniqueness constraint on (generation_id) in prompt_variants or
    rag_configs as of the current Alembic migration set.  Two concurrent calls
    will both succeed and double-insert every child row.

    This test is intentionally left failing (or skipped) to track the issue.
    Fix: add UNIQUE(generation_id) on rag_configs and a guard in
    save_generate_result (e.g. SELECT FOR UPDATE on the parent Generation row
    before inserting children, or check that status == 'pending' before proceeding).
    """
    import asyncio
    from src.loop.generate.repository import (
        create_pending_generation,
        save_generate_result,
        get_generation_summary,
    )

    gen_id = uuid.uuid4()
    await create_pending_generation(db_session, inference_row.id, gen_id)

    result = _make_result(inference_id=inference_row.id)

    # Simulate two concurrent callers
    await asyncio.gather(
        save_generate_result(db_session, gen_id, result),
        save_generate_result(db_session, gen_id, result),
    )

    summary = await get_generation_summary(db_session, inference_row.id)
    assert summary is not None
    # Each list had 1 item → expect exactly 1 variant and 1 eval pair, NOT 2
    assert summary["variant_count"] == 1, (
        f"Expected 1 variant but got {summary['variant_count']} — double-insert bug!"
    )
    assert summary["eval_count"] == 1, (
        f"Expected 1 eval pair but got {summary['eval_count']} — double-insert bug!"
    )
