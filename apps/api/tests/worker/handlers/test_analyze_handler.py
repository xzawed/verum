"""Unit tests for the ANALYZE job handler."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.worker.handlers.analyze import handle_analyze


def _make_analysis_result(call_site_count: int = 3):
    from src.loop.analyze.models import AnalysisResult
    result = MagicMock(spec=AnalysisResult)
    result.call_sites = [MagicMock()] * call_site_count
    result.language_breakdown = {"python": 80, "typescript": 20}
    return result


@pytest.mark.asyncio
async def test_handle_analyze_happy_path() -> None:
    """Successful analysis enqueues INFER job and commits."""
    db = AsyncMock()
    repo_id = uuid.uuid4()
    analysis_id = uuid.uuid4()
    analysis_result = _make_analysis_result(call_site_count=5)

    with patch("src.worker.handlers.analyze.run_analysis", new=AsyncMock(return_value=analysis_result)), \
         patch("src.worker.handlers.analyze.save_analysis_result", new=AsyncMock()), \
         patch("src.worker.handlers.analyze.enqueue_next", new=AsyncMock()) as mock_enq:

        result = await handle_analyze(
            db=db,
            owner_user_id=uuid.uuid4(),
            payload={
                "repo_url": "https://github.com/xzawed/ArcanaInsight",
                "branch": "main",
                "repo_id": str(repo_id),
                "analysis_id": str(analysis_id),
            },
        )

    assert result["analysis_id"] == str(analysis_id)
    assert result["call_site_count"] == 5
    mock_enq.assert_awaited_once()
    enq_call = mock_enq.await_args.kwargs
    assert enq_call["kind"] == "infer"
    assert "analysis_id" in enq_call["payload"]
    assert "inference_id" in enq_call["payload"]
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_analyze_calls_mark_error_on_failure() -> None:
    """When run_analysis raises, mark_analysis_error is called and exception re-raises."""
    db = AsyncMock()
    analysis_id = uuid.uuid4()

    with patch("src.worker.handlers.analyze.run_analysis", side_effect=RuntimeError("clone failed")), \
         patch("src.worker.handlers.analyze.mark_analysis_error", new=AsyncMock()) as mock_mark, \
         patch("src.worker.handlers.analyze.enqueue_next", new=AsyncMock()) as mock_enq:

        with pytest.raises(RuntimeError, match="clone failed"):
            await handle_analyze(
                db=db,
                owner_user_id=uuid.uuid4(),
                payload={
                    "repo_url": "https://github.com/xzawed/ArcanaInsight",
                    "repo_id": str(uuid.uuid4()),
                    "analysis_id": str(analysis_id),
                },
            )

    mock_mark.assert_awaited_once()
    assert mock_mark.await_args.args[1] == analysis_id
    mock_enq.assert_not_awaited()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_analyze_uses_default_branch() -> None:
    """Branch defaults to 'main' when not provided in payload."""
    db = AsyncMock()
    analysis_result = _make_analysis_result()
    captured: dict = {}

    async def _fake_run_analysis(repo_url, *, branch, repo_id):
        captured["branch"] = branch
        return analysis_result

    with patch("src.worker.handlers.analyze.run_analysis", side_effect=_fake_run_analysis), \
         patch("src.worker.handlers.analyze.save_analysis_result", new=AsyncMock()), \
         patch("src.worker.handlers.analyze.enqueue_next", new=AsyncMock()):

        await handle_analyze(
            db=db,
            owner_user_id=uuid.uuid4(),
            payload={
                "repo_url": "https://github.com/xzawed/ArcanaInsight",
                "repo_id": str(uuid.uuid4()),
                "analysis_id": str(uuid.uuid4()),
            },
        )

    assert captured["branch"] == "main"


@pytest.mark.asyncio
async def test_handle_analyze_rejects_non_github_url() -> None:
    """Non-GitHub URL in payload raises ValueError before any analysis runs."""
    db = AsyncMock()
    with pytest.raises(ValueError, match="Rejected non-GitHub URL"):
        await handle_analyze(
            db=db,
            owner_user_id=uuid.uuid4(),
            payload={
                "repo_url": "https://gitlab.com/user/repo",
                "repo_id": str(uuid.uuid4()),
                "analysis_id": str(uuid.uuid4()),
            },
        )


@pytest.mark.asyncio
async def test_handle_analyze_rejects_unsafe_branch() -> None:
    """Branch name with shell-special characters raises ValueError."""
    db = AsyncMock()
    with pytest.raises(ValueError, match="Rejected unsafe branch name"):
        await handle_analyze(
            db=db,
            owner_user_id=uuid.uuid4(),
            payload={
                "repo_url": "https://github.com/xzawed/ArcanaInsight",
                "branch": "feat; rm -rf /",
                "repo_id": str(uuid.uuid4()),
                "analysis_id": str(uuid.uuid4()),
            },
        )
