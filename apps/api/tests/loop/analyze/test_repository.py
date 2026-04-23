"""Unit tests for the ANALYZE stage repository (src.loop.analyze.repository)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.loop.analyze.models import AnalysisResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_analysis_result(repo_id: uuid.UUID | None = None) -> AnalysisResult:
    return AnalysisResult(
        repo_id=repo_id or uuid.uuid4(),
        call_sites=[],
        prompt_templates=[],
        model_configs=[],
        language_breakdown={"python": 100},
        analyzed_at=datetime.now(timezone.utc),
    )


def _make_mock_repo(repo_id: uuid.UUID, owner_user_id: uuid.UUID) -> MagicMock:
    repo = MagicMock()
    repo.id = repo_id
    repo.owner_user_id = owner_user_id
    repo.github_url = "https://github.com/xzawed/test"
    repo.default_branch = "main"
    return repo


def _make_mock_analysis(analysis_id: uuid.UUID, repo_id: uuid.UUID) -> MagicMock:
    analysis = MagicMock()
    analysis.id = analysis_id
    analysis.repo_id = repo_id
    analysis.status = "pending"
    return analysis


# ---------------------------------------------------------------------------
# get_or_create_repo
# ---------------------------------------------------------------------------

async def test_get_or_create_repo_returns_existing_when_found(
    mock_db: AsyncMock, owner_user_id: uuid.UUID
) -> None:
    """get_or_create_repo returns existing repo without insert when URL+owner match."""
    from src.loop.analyze.repository import get_or_create_repo

    repo_id = uuid.uuid4()
    existing = _make_mock_repo(repo_id, owner_user_id)

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = existing
    mock_db.execute = AsyncMock(return_value=result_mock)

    returned = await get_or_create_repo(
        mock_db, "https://github.com/xzawed/test", owner_user_id=owner_user_id
    )

    assert returned.id == repo_id
    mock_db.add.assert_not_called()
    mock_db.flush.assert_not_awaited()


async def test_get_or_create_repo_inserts_when_not_found(
    mock_db: AsyncMock, owner_user_id: uuid.UUID
) -> None:
    """get_or_create_repo creates a new Repo row when no match exists."""
    from src.loop.analyze.repository import get_or_create_repo

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=result_mock)

    await get_or_create_repo(
        mock_db, "https://github.com/xzawed/new-repo", owner_user_id=owner_user_id
    )

    mock_db.add.assert_called_once()
    mock_db.flush.assert_awaited_once()


async def test_get_or_create_repo_uses_provided_branch(
    mock_db: AsyncMock, owner_user_id: uuid.UUID
) -> None:
    """Branch parameter is passed through when creating a new repo."""
    from src.loop.analyze.repository import get_or_create_repo

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=result_mock)

    await get_or_create_repo(
        mock_db,
        "https://github.com/xzawed/test",
        branch="develop",
        owner_user_id=owner_user_id,
    )

    added_repo = mock_db.add.call_args.args[0]
    assert added_repo.default_branch == "develop"


# ---------------------------------------------------------------------------
# create_pending_analysis
# ---------------------------------------------------------------------------

async def test_create_pending_analysis_sets_status_pending(
    mock_db: AsyncMock,
) -> None:
    """create_pending_analysis inserts an Analysis row with status='pending'."""
    from src.loop.analyze.repository import create_pending_analysis

    await create_pending_analysis(mock_db, uuid.uuid4())

    mock_db.add.assert_called_once()
    analysis = mock_db.add.call_args.args[0]
    assert analysis.status == "pending"
    mock_db.flush.assert_awaited_once()
    mock_db.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# save_analysis_result
# ---------------------------------------------------------------------------

async def test_save_analysis_result_transitions_status_to_done(
    mock_db: AsyncMock,
) -> None:
    """save_analysis_result sets status='done' and attaches structured fields."""
    from src.loop.analyze.repository import save_analysis_result

    analysis_id = uuid.uuid4()
    result = _make_analysis_result()

    mock_analysis = _make_mock_analysis(analysis_id, result.repo_id)
    mock_repo = MagicMock()
    mock_repo.last_analyzed_at = None

    select_analysis = MagicMock()
    select_analysis.scalar_one.return_value = mock_analysis
    select_repo = MagicMock()
    select_repo.scalar_one_or_none.return_value = mock_repo

    mock_db.execute = AsyncMock(side_effect=[select_analysis, select_repo])

    await save_analysis_result(mock_db, analysis_id, result)

    assert mock_analysis.status == "done"
    assert mock_analysis.call_sites == []
    assert mock_analysis.prompt_templates == []
    assert mock_repo.last_analyzed_at is not None


async def test_save_analysis_result_when_repo_missing_does_not_raise(
    mock_db: AsyncMock,
) -> None:
    """save_analysis_result succeeds even if repo row is not found."""
    from src.loop.analyze.repository import save_analysis_result

    analysis_id = uuid.uuid4()
    result = _make_analysis_result()

    mock_analysis = _make_mock_analysis(analysis_id, result.repo_id)

    select_analysis = MagicMock()
    select_analysis.scalar_one.return_value = mock_analysis
    select_repo = MagicMock()
    select_repo.scalar_one_or_none.return_value = None

    mock_db.execute = AsyncMock(side_effect=[select_analysis, select_repo])

    await save_analysis_result(mock_db, analysis_id, result)

    assert mock_analysis.status == "done"


# ---------------------------------------------------------------------------
# get_analysis / list_repo_analyses
# ---------------------------------------------------------------------------

async def test_get_analysis_returns_none_when_missing(mock_db: AsyncMock) -> None:
    """get_analysis returns None for an unknown analysis_id."""
    from src.loop.analyze.repository import get_analysis

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=result_mock)

    result = await get_analysis(mock_db, uuid.uuid4())
    assert result is None


async def test_list_repo_analyses_returns_empty_list_when_none(
    mock_db: AsyncMock,
) -> None:
    """list_repo_analyses returns [] when no analyses exist for a repo."""
    from src.loop.analyze.repository import list_repo_analyses

    scalars_mock = MagicMock()
    scalars_mock.all.return_value = []
    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock
    mock_db.execute = AsyncMock(return_value=result_mock)

    rows = await list_repo_analyses(mock_db, uuid.uuid4())
    assert rows == []
