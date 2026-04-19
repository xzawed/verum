"""Tests for INFER stage API router."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import ASGITransport, AsyncClient

from src.main import app


async def test_start_infer_404_when_analysis_missing() -> None:
    missing_id = uuid.uuid4()
    with patch("src.loop.infer.router.get_analysis", new=AsyncMock(return_value=None)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(f"/v1/infer/{missing_id}")
    assert response.status_code == 404


async def test_start_infer_409_when_analysis_not_done() -> None:
    analysis_id = uuid.uuid4()
    mock_analysis = MagicMock()
    mock_analysis.status = "pending"

    with patch("src.loop.infer.router.get_analysis", new=AsyncMock(return_value=mock_analysis)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(f"/v1/infer/{analysis_id}")
    assert response.status_code == 409


async def test_start_infer_returns_202() -> None:
    analysis_id = uuid.uuid4()
    inference_id = uuid.uuid4()

    mock_analysis = MagicMock()
    mock_analysis.status = "done"
    mock_analysis.repo_id = uuid.uuid4()

    mock_inference = MagicMock()
    mock_inference.id = inference_id

    with (
        patch("src.loop.infer.router.get_analysis", new=AsyncMock(return_value=mock_analysis)),
        patch("src.loop.infer.router.create_pending_inference", new=AsyncMock(return_value=mock_inference)),
        patch("src.loop.infer.router._run_infer_background", new=AsyncMock()),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(f"/v1/infer/{analysis_id}")

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "pending"
    assert "inference_id" in body


async def test_get_infer_404_when_missing() -> None:
    missing_id = uuid.uuid4()
    with patch("src.loop.infer.router.get_inference", new=AsyncMock(return_value=None)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/v1/infer/{missing_id}")
    assert response.status_code == 404


async def test_get_infer_done_returns_domain() -> None:
    inference_id = uuid.uuid4()
    mock_row = MagicMock()
    mock_row.id = inference_id
    mock_row.status = "done"
    mock_row.analysis_id = uuid.uuid4()
    mock_row.repo_id = uuid.uuid4()
    mock_row.domain = "divination/tarot"
    mock_row.tone = "mystical"
    mock_row.language = "ko"
    mock_row.user_type = "consumer"
    mock_row.confidence = 0.92
    mock_row.summary = "A tarot service."
    mock_row.error = None

    with (
        patch("src.loop.infer.router.get_inference", new=AsyncMock(return_value=mock_row)),
        patch("src.loop.infer.router.get_harvest_sources", new=AsyncMock(return_value=[])),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/v1/infer/{inference_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["domain"] == "divination/tarot"
    assert body["confidence"] == 0.92
