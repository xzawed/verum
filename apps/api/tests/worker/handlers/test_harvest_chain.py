"""Unit tests for the HARVEST→GENERATE handler chain."""
from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.worker.handlers.harvest import handle_harvest
from src.worker.handlers.generate import handle_generate


# ---------------------------------------------------------------------------
# Scenario 1: Normal flow — harvest completes, generation row created, job enqueued
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_harvest_chain_normal_flow() -> None:
    """Full happy-path: all sources succeed → generation row committed → job enqueued."""
    db = AsyncMock()

    with patch("src.worker.handlers.harvest.harvest_source", new=AsyncMock(return_value=10)), \
         patch("src.worker.handlers.harvest.get_or_create_quota", new=AsyncMock(
             return_value={"plan": "free", "chunks_stored": 0}
         )), \
         patch("src.worker.handlers.harvest.create_pending_generation", new=AsyncMock()) as mock_cpg, \
         patch("src.worker.handlers.harvest.enqueue_next", new=AsyncMock()) as mock_enq, \
         patch("src.worker.handlers.harvest.increment_quota", new=AsyncMock()):

        result = await handle_harvest(
            db=db,
            owner_user_id=uuid.uuid4(),
            payload={
                "inference_id": str(uuid.uuid4()),
                "source_ids": [
                    [str(uuid.uuid4()), "https://example.com/source1"],
                    [str(uuid.uuid4()), "https://example.com/source2"],
                ],
            },
        )

    assert result["total_chunks"] == 20
    assert result["successful_sources"] == 2
    mock_cpg.assert_awaited_once()
    mock_enq.assert_awaited_once()
    enq_call = mock_enq.await_args
    assert enq_call.kwargs["kind"] == "generate"
    assert "inference_id" in enq_call.kwargs["payload"]
    assert "generation_id" in enq_call.kwargs["payload"]
    db.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# Scenario 2: All harvest sources errored — RuntimeError raised, chain aborted
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_harvest_chain_aborts_when_all_sources_fail() -> None:
    """RuntimeError is raised when every source fails — chain does NOT fire."""
    db = AsyncMock()

    async def _failing_source(db_, source_id, url, inference_id, **kwargs):
        raise RuntimeError("connection refused")

    with patch("src.worker.handlers.harvest.harvest_source", side_effect=_failing_source), \
         patch("src.worker.handlers.harvest.create_pending_generation", new=AsyncMock()) as mock_cpg, \
         patch("src.worker.handlers.harvest.enqueue_next", new=AsyncMock()) as mock_enq:

        with pytest.raises(RuntimeError, match="no usable content"):
            await handle_harvest(
                db=db,
                owner_user_id=uuid.uuid4(),
                payload={
                    "inference_id": str(uuid.uuid4()),
                    "source_ids": [[str(uuid.uuid4()), "https://bad.host/"]],
                },
            )

    mock_cpg.assert_not_awaited()
    mock_enq.assert_not_awaited()
    db.commit.assert_not_awaited()


# ---------------------------------------------------------------------------
# Scenario 3: create_pending_generation raises — enqueue_next must NOT run
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_harvest_chain_create_pending_generation_raises_aborts_enqueue() -> None:
    """If create_pending_generation raises, enqueue_next must not be called."""
    db = AsyncMock()

    with patch("src.worker.handlers.harvest.harvest_source", new=AsyncMock(return_value=5)), \
         patch("src.worker.handlers.harvest.get_or_create_quota", new=AsyncMock(
             return_value={"plan": "free", "chunks_stored": 0}
         )), \
         patch(
             "src.worker.handlers.harvest.create_pending_generation",
             side_effect=Exception("FK violation: inference_id not found"),
         ) as mock_cpg, \
         patch("src.worker.handlers.harvest.enqueue_next", new=AsyncMock()) as mock_enq, \
         patch("src.worker.handlers.harvest.increment_quota", new=AsyncMock()):

        with pytest.raises(Exception, match="FK violation"):
            await handle_harvest(
                db=db,
                owner_user_id=uuid.uuid4(),
                payload={
                    "inference_id": str(uuid.uuid4()),
                    "source_ids": [[str(uuid.uuid4()), "https://ok.com/"]],
                },
            )

    mock_enq.assert_not_awaited()
    db.commit.assert_not_awaited()


# ---------------------------------------------------------------------------
# Scenario 4: handle_generate called with non-existent inference_id
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_handler_raises_on_missing_inference() -> None:
    """handle_generate raises ValueError when inference_id is not in the DB."""
    db = AsyncMock()
    inference_id = uuid.uuid4()

    empty_result = MagicMock()
    empty_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=empty_result)

    with patch("src.worker.handlers.generate.run_generate", new=AsyncMock()) as mock_rg, \
         patch("src.worker.handlers.generate.mark_generate_error", new=AsyncMock()) as mock_mge:

        with pytest.raises(ValueError, match=str(inference_id)):
            await handle_generate(
                db=db,
                owner_user_id=uuid.uuid4(),
                payload={
                    "inference_id": str(inference_id),
                    "generation_id": str(uuid.uuid4()),
                },
            )

    mock_rg.assert_not_awaited()
    mock_mge.assert_not_awaited()


# ---------------------------------------------------------------------------
# Scenario 5: handle_generate — save fails → mark_generate_error called
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_handler_calls_mark_error_when_save_fails() -> None:
    """When save_generate_result raises, mark_generate_error is called and exception re-raises."""
    from sqlalchemy.exc import NoResultFound

    db = AsyncMock()
    inference_id = uuid.uuid4()
    generation_id = uuid.uuid4()

    mock_inference = MagicMock()
    mock_inference.id = inference_id
    mock_inference.analysis_id = uuid.uuid4()
    mock_inference.domain = "tarot_divination"
    mock_inference.tone = "mystical"
    mock_inference.language = "ko"
    mock_inference.user_type = "consumer"
    mock_inference.summary = "ArcanaInsight tarot reading service"

    inference_result = MagicMock()
    inference_result.scalar_one_or_none.return_value = mock_inference

    analysis_result = MagicMock()
    analysis_result.fetchone.return_value = ([], )

    chunk_result = MagicMock()
    chunk_result.fetchall.return_value = []

    db.execute = AsyncMock(
        side_effect=[inference_result, analysis_result, chunk_result]
    )

    mock_generate_result = MagicMock()
    mock_generate_result.prompt_variants = []
    mock_generate_result.eval_pairs = []
    mock_generate_result.rag_config = MagicMock(chunking_strategy="recursive")

    with patch("src.worker.handlers.generate.run_generate", new=AsyncMock(return_value=mock_generate_result)), \
         patch(
             "src.worker.handlers.generate.save_generate_result",
             side_effect=NoResultFound("Generation row absent"),
         ), \
         patch("src.worker.handlers.generate.mark_generate_error", new=AsyncMock()) as mock_mge:

        with pytest.raises(NoResultFound):
            await handle_generate(
                db=db,
                owner_user_id=uuid.uuid4(),
                payload={
                    "inference_id": str(inference_id),
                    "generation_id": str(generation_id),
                },
            )

    mock_mge.assert_awaited_once()
    assert mock_mge.await_args.args[1] == generation_id
