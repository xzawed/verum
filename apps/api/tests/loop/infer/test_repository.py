"""Unit tests for the INFER stage repository (src.loop.infer.repository)."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.loop.infer.models import ServiceInference, SuggestedSource


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_inference(inference_id: uuid.UUID, repo_id: uuid.UUID) -> MagicMock:
    obj = MagicMock()
    obj.id = inference_id
    obj.repo_id = repo_id
    obj.status = "pending"
    obj.domain = None
    obj.tone = None
    obj.language = None
    obj.user_type = None
    obj.confidence = None
    obj.summary = None
    obj.raw_response = None
    return obj


def _make_service_inference(repo_id: uuid.UUID | None = None) -> ServiceInference:
    return ServiceInference(
        repo_id=repo_id or uuid.uuid4(),
        analysis_id=uuid.uuid4(),
        domain="divination/tarot",
        tone="mystical",
        language="ko",
        user_type="consumer",
        confidence=0.95,
        summary="Tarot reading service",
        suggested_sources=[
            SuggestedSource(
                url="https://en.wikipedia.org/wiki/Tarot",
                title="Tarot - Wikipedia",
                description="Overview of tarot divination system",
            )
        ],
    )


# ---------------------------------------------------------------------------
# create_pending_inference
# ---------------------------------------------------------------------------

async def test_create_pending_inference_adds_with_pending_status(
    mock_db: AsyncMock,
) -> None:
    """create_pending_inference inserts a row with status='pending' and returns it."""
    from src.loop.infer.repository import create_pending_inference

    row = await create_pending_inference(mock_db, uuid.uuid4(), uuid.uuid4())

    mock_db.add.assert_called_once()
    added = mock_db.add.call_args.args[0]
    assert added.status == "pending"
    mock_db.flush.assert_awaited_once()
    mock_db.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# save_inference_result
# ---------------------------------------------------------------------------

async def test_save_inference_result_transitions_to_done(
    mock_db: AsyncMock,
) -> None:
    """save_inference_result sets status='done' and writes all domain fields."""
    from src.loop.infer.repository import save_inference_result

    inference_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    mock_inference = _make_inference(inference_id, repo_id)
    result = _make_service_inference(repo_id)

    select_result = MagicMock()
    select_result.scalar_one.return_value = mock_inference
    mock_db.execute = AsyncMock(return_value=select_result)

    await save_inference_result(mock_db, inference_id, result, raw={"domain": "divination/tarot"})

    assert mock_inference.status == "done"
    assert mock_inference.domain == "divination/tarot"
    assert mock_inference.tone == "mystical"
    assert mock_inference.language == "ko"
    assert mock_inference.user_type == "consumer"
    assert mock_inference.confidence == pytest.approx(0.95)
    mock_db.commit.assert_awaited_once()


async def test_save_inference_result_persists_suggested_sources(
    mock_db: AsyncMock,
) -> None:
    """One HarvestSource row is added for each suggested_source in the result."""
    from src.loop.infer.repository import save_inference_result

    inference_id = uuid.uuid4()
    result = _make_service_inference()

    select_result = MagicMock()
    select_result.scalar_one.return_value = _make_inference(inference_id, result.repo_id)
    mock_db.execute = AsyncMock(return_value=select_result)

    await save_inference_result(mock_db, inference_id, result, raw={})

    # mock_db.add: 1 for each suggested source (1 in _make_service_inference)
    assert mock_db.add.call_count == len(result.suggested_sources)


# ---------------------------------------------------------------------------
# get_inference
# ---------------------------------------------------------------------------

async def test_get_inference_returns_none_for_unknown_id(mock_db: AsyncMock) -> None:
    """get_inference returns None for a non-existent inference_id."""
    from src.loop.infer.repository import get_inference

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=result_mock)

    result = await get_inference(mock_db, uuid.uuid4())
    assert result is None


# ---------------------------------------------------------------------------
# list_analysis_inferences
# ---------------------------------------------------------------------------

async def test_list_analysis_inferences_returns_ordered_rows(mock_db: AsyncMock) -> None:
    """list_analysis_inferences returns all inferences for a given analysis_id."""
    from src.loop.infer.repository import list_analysis_inferences

    inference_id = uuid.uuid4()
    mock_row = _make_inference(inference_id, uuid.uuid4())

    scalars_mock = MagicMock()
    scalars_mock.all.return_value = [mock_row]
    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock
    mock_db.execute = AsyncMock(return_value=result_mock)

    rows = await list_analysis_inferences(mock_db, uuid.uuid4())
    assert len(rows) == 1
    assert rows[0].id == inference_id


# ---------------------------------------------------------------------------
# approve_source / reject_source
# ---------------------------------------------------------------------------

async def test_approve_source_sets_status_approved(mock_db: AsyncMock) -> None:
    """approve_source transitions a HarvestSource to 'approved' and commits."""
    from src.loop.infer.repository import approve_source

    mock_source = MagicMock()
    mock_source.status = "proposed"

    result_mock = MagicMock()
    result_mock.scalar_one.return_value = mock_source
    mock_db.execute = AsyncMock(return_value=result_mock)

    returned = await approve_source(mock_db, uuid.uuid4())

    assert returned.status == "approved"
    mock_db.commit.assert_awaited_once()


async def test_reject_source_sets_status_rejected(mock_db: AsyncMock) -> None:
    """reject_source transitions a HarvestSource to 'rejected' and commits."""
    from src.loop.infer.repository import reject_source

    mock_source = MagicMock()
    mock_source.status = "proposed"

    result_mock = MagicMock()
    result_mock.scalar_one.return_value = mock_source
    mock_db.execute = AsyncMock(return_value=result_mock)

    returned = await reject_source(mock_db, uuid.uuid4())

    assert returned.status == "rejected"
    mock_db.commit.assert_awaited_once()
