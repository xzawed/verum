"""Tests for the ANALYZE stage API router (F-1.8)."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.fixture
def mock_db():
    """Return a mock AsyncSession that satisfies Depends(get_db)."""
    session = AsyncMock()
    return session


async def test_start_analyze_returns_202() -> None:
    mock_repo = MagicMock()
    mock_repo.id = uuid.uuid4()

    mock_analysis = MagicMock()
    mock_analysis.id = uuid.uuid4()

    with (
        patch("src.loop.analyze.router.get_or_create_repo", new=AsyncMock(return_value=mock_repo)),
        patch("src.loop.analyze.router.create_pending_analysis", new=AsyncMock(return_value=mock_analysis)),
        patch("src.loop.analyze.router._run_analysis_background", new=AsyncMock()),
        patch("src.db.session.AsyncSessionLocal"),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/v1/analyze",
                json={"repo_url": "https://github.com/xzawed/ArcanaInsight", "branch": "main"},
            )

    assert response.status_code == 202
    body = response.json()
    assert "analysis_id" in body
    assert body["status"] == "pending"


async def test_get_analyze_result_404_on_missing() -> None:
    missing_id = uuid.uuid4()

    with patch("src.loop.analyze.router.get_analysis", new=AsyncMock(return_value=None)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/v1/analyze/{missing_id}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Analysis not found"


async def test_get_analyze_result_pending() -> None:
    analysis_id = uuid.uuid4()
    mock_row = MagicMock()
    mock_row.id = analysis_id
    mock_row.status = "pending"
    mock_row.started_at = None

    with patch("src.loop.analyze.router.get_analysis", new=AsyncMock(return_value=mock_row)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/v1/analyze/{analysis_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending"
    assert str(analysis_id) == body["analysis_id"]


async def test_get_analyze_result_done() -> None:
    from datetime import datetime, timezone

    analysis_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    mock_row = MagicMock()
    mock_row.id = analysis_id
    mock_row.repo_id = repo_id
    mock_row.status = "done"
    mock_row.call_sites = [{"file_path": "a.ts", "line": 1, "sdk": "grok", "function": "fetch"}]
    mock_row.prompt_templates = []
    mock_row.model_configs = []
    mock_row.language_breakdown = {"ts": 10}
    mock_row.analyzed_at = datetime(2026, 4, 19, 0, 0, 0, tzinfo=timezone.utc)

    with patch("src.loop.analyze.router.get_analysis", new=AsyncMock(return_value=mock_row)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/v1/analyze/{analysis_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "done"
    assert len(body["call_sites"]) == 1
    assert body["call_sites"][0]["sdk"] == "grok"


async def test_list_analyses_for_repo() -> None:
    from datetime import datetime, timezone

    repo_id = uuid.uuid4()
    analysis_id = uuid.uuid4()

    mock_row = MagicMock()
    mock_row.id = analysis_id
    mock_row.status = "done"
    mock_row.call_sites = [1, 2, 3]
    mock_row.analyzed_at = datetime(2026, 4, 19, tzinfo=timezone.utc)

    with patch("src.loop.analyze.router.list_repo_analyses", new=AsyncMock(return_value=[mock_row])):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/v1/repos/{repo_id}/analyses")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["call_site_count"] == 3
    assert body[0]["status"] == "done"
