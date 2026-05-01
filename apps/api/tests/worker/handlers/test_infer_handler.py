"""Unit tests for the INFER job handler."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.loop.quota import QuotaExceededError
from src.worker.handlers.infer import handle_infer


def _make_analysis():
    m = MagicMock()
    m.id = uuid.uuid4()
    m.repo_id = uuid.uuid4()
    m.call_sites = []
    m.prompt_templates = []
    m.model_configs = []
    m.language_breakdown = {"python": 100}
    m.analyzed_at = None
    return m


def _make_infer_result(domain: str = "tarot_divination"):
    m = MagicMock()
    m.domain = domain
    m.tone = "mystical"
    m.language = "ko"
    m.user_type = "consumer"
    m.confidence = 0.92
    m.summary = "Tarot reading service"
    m.harvest_sources = [{"url": "https://example.com", "title": "Tarot reference"}]
    return m


@pytest.mark.asyncio
async def test_handle_infer_enqueues_harvest_when_sources_exist() -> None:
    """INFER enqueues HARVEST job when approved harvest sources are found."""
    db = AsyncMock()
    analysis_id = uuid.uuid4()
    inference_id = uuid.uuid4()
    analysis = _make_analysis()
    infer_result = _make_infer_result()

    source_id = uuid.uuid4()
    analysis_result_mock = MagicMock()
    analysis_result_mock.scalar_one_or_none.return_value = analysis

    update_result = MagicMock()
    rows_result = MagicMock()
    rows_result.fetchall.return_value = [(source_id, "https://example.com")]

    db.execute = AsyncMock(side_effect=[analysis_result_mock, update_result, rows_result])

    with patch("src.worker.handlers.infer.check_quota", new=AsyncMock()), \
         patch("src.worker.handlers.infer.run_infer", new=AsyncMock(return_value=infer_result)), \
         patch("src.worker.handlers.infer.save_inference_result", new=AsyncMock()), \
         patch("src.worker.handlers.infer.enqueue_next", new=AsyncMock()) as mock_enq:

        result = await handle_infer(
            db=db,
            owner_user_id=uuid.uuid4(),
            payload={
                "analysis_id": str(analysis_id),
                "inference_id": str(inference_id),
            },
        )

    assert result["inference_id"] == str(inference_id)
    assert result["domain"] == "tarot_divination"
    mock_enq.assert_awaited_once()
    assert mock_enq.await_args.kwargs["kind"] == "harvest"


@pytest.mark.asyncio
async def test_handle_infer_skips_harvest_when_no_sources() -> None:
    """INFER does NOT enqueue HARVEST when no approved sources are found."""
    db = AsyncMock()
    analysis = _make_analysis()
    infer_result = _make_infer_result()

    analysis_result_mock = MagicMock()
    analysis_result_mock.scalar_one_or_none.return_value = analysis

    update_result = MagicMock()
    rows_result = MagicMock()
    rows_result.fetchall.return_value = []

    db.execute = AsyncMock(side_effect=[analysis_result_mock, update_result, rows_result])

    with patch("src.worker.handlers.infer.check_quota", new=AsyncMock()), \
         patch("src.worker.handlers.infer.run_infer", new=AsyncMock(return_value=infer_result)), \
         patch("src.worker.handlers.infer.save_inference_result", new=AsyncMock()), \
         patch("src.worker.handlers.infer.enqueue_next", new=AsyncMock()) as mock_enq:

        await handle_infer(
            db=db,
            owner_user_id=uuid.uuid4(),
            payload={
                "analysis_id": str(uuid.uuid4()),
                "inference_id": str(uuid.uuid4()),
            },
        )

    mock_enq.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_infer_raises_when_analysis_missing() -> None:
    """ValueError is raised when analysis_id is not found in the DB."""
    db = AsyncMock()
    analysis_id = uuid.uuid4()

    missing_result = MagicMock()
    missing_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=missing_result)

    with patch("src.worker.handlers.infer.run_infer", new=AsyncMock()) as mock_ri, \
         patch("src.worker.handlers.infer.mark_inference_error", new=AsyncMock()) as mock_mie:

        with pytest.raises(ValueError, match=str(analysis_id)):
            await handle_infer(
                db=db,
                owner_user_id=uuid.uuid4(),
                payload={
                    "analysis_id": str(analysis_id),
                    "inference_id": str(uuid.uuid4()),
                },
            )

    mock_ri.assert_not_awaited()
    mock_mie.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_infer_calls_mark_error_on_failure() -> None:
    """mark_inference_error is called and exception re-raises when run_infer fails."""
    db = AsyncMock()
    analysis = _make_analysis()
    inference_id = uuid.uuid4()

    analysis_result_mock = MagicMock()
    analysis_result_mock.scalar_one_or_none.return_value = analysis
    db.execute = AsyncMock(return_value=analysis_result_mock)

    with patch("src.worker.handlers.infer.check_quota", new=AsyncMock()), \
         patch("src.worker.handlers.infer.run_infer", side_effect=RuntimeError("LLM error")), \
         patch("src.worker.handlers.infer.mark_inference_error", new=AsyncMock()) as mock_mie:

        with pytest.raises(RuntimeError, match="LLM error"):
            await handle_infer(
                db=db,
                owner_user_id=uuid.uuid4(),
                payload={
                    "analysis_id": str(uuid.uuid4()),
                    "inference_id": str(inference_id),
                },
            )

    mock_mie.assert_awaited_once()
    assert mock_mie.await_args.args[1] == inference_id


@pytest.mark.asyncio
async def test_handle_infer_raises_when_quota_exceeded() -> None:
    """QuotaExceededError from check_quota causes mark_inference_error + re-raise."""
    db = AsyncMock()
    analysis = _make_analysis()
    inference_id = uuid.uuid4()

    analysis_result_mock = MagicMock()
    analysis_result_mock.scalar_one_or_none.return_value = analysis
    db.execute = AsyncMock(return_value=analysis_result_mock)

    quota_error = QuotaExceededError("chunks", 500, 500)

    with patch("src.worker.handlers.infer.check_quota", side_effect=quota_error), \
         patch("src.worker.handlers.infer.run_infer", new=AsyncMock()) as mock_ri, \
         patch("src.worker.handlers.infer.mark_inference_error", new=AsyncMock()) as mock_mie:

        with pytest.raises(QuotaExceededError):
            await handle_infer(
                db=db,
                owner_user_id=uuid.uuid4(),
                payload={
                    "analysis_id": str(uuid.uuid4()),
                    "inference_id": str(inference_id),
                },
            )

    mock_ri.assert_not_awaited()
    mock_mie.assert_awaited_once()
    assert mock_mie.await_args.args[1] == inference_id
