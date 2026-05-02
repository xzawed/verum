"""Unit tests for webhook handler."""
from __future__ import annotations

import hashlib
import hmac
import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest


@pytest.fixture()
def mock_db() -> AsyncMock:
    return AsyncMock()


@pytest.fixture()
def subscription_row() -> dict:
    return {"url": "https://example.com/hook", "signing_secret": "test_secret_abc123"}


@pytest.mark.asyncio
async def test_delivers_with_correct_hmac(
    mock_db: AsyncMock, subscription_row: dict
) -> None:
    from src.worker.handlers.webhook import handle_webhook

    result_mock = MagicMock()
    result_mock.mappings.return_value.first.return_value = subscription_row
    mock_db.execute = AsyncMock(return_value=result_mock)

    resp_mock = MagicMock()
    resp_mock.status_code = 200
    resp_mock.raise_for_status = MagicMock()

    with patch("src.worker.handlers.webhook.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=resp_mock)
        mock_cls.return_value = mock_client

        result = await handle_webhook(
            mock_db,
            UUID("00000000-0000-0000-0000-000000000099"),
            {
                "subscription_id": str(UUID("00000000-0000-0000-0000-000000000001")),
                "event": "experiment.winner_promoted",
                "data": {"deployment_id": "dep-1", "winner_variant": "v2", "confidence": 0.97},
            },
        )

    assert result["delivered"] is True
    assert result["status_code"] == 200

    call_kwargs = mock_client.post.call_args.kwargs
    sent_body: str = call_kwargs["content"]
    sig_header: str = call_kwargs["headers"]["X-Verum-Signature"]
    expected = "sha256=" + hmac.new(
        b"test_secret_abc123", sent_body.encode(), hashlib.sha256
    ).hexdigest()
    assert sig_header == expected


@pytest.mark.asyncio
async def test_skips_inactive_subscription(mock_db: AsyncMock) -> None:
    from src.worker.handlers.webhook import handle_webhook

    result_mock = MagicMock()
    result_mock.mappings.return_value.first.return_value = None
    mock_db.execute = AsyncMock(return_value=result_mock)

    with patch("src.worker.handlers.webhook.httpx.AsyncClient") as mock_cls:
        result = await handle_webhook(
            mock_db,
            UUID("00000000-0000-0000-0000-000000000099"),
            {
                "subscription_id": str(UUID("00000000-0000-0000-0000-000000000001")),
                "event": "experiment.winner_promoted",
                "data": {},
            },
        )
        mock_cls.assert_not_called()

    assert result["skipped"] == "subscription not found or inactive"


@pytest.mark.asyncio
async def test_propagates_http_error(
    mock_db: AsyncMock, subscription_row: dict
) -> None:
    import httpx
    from src.worker.handlers.webhook import handle_webhook

    result_mock = MagicMock()
    result_mock.mappings.return_value.first.return_value = subscription_row
    mock_db.execute = AsyncMock(return_value=result_mock)

    with patch("src.worker.handlers.webhook.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "500 Server Error", request=MagicMock(), response=MagicMock()
            )
        )
        mock_cls.return_value = mock_client

        with pytest.raises(httpx.HTTPStatusError):
            await handle_webhook(
                mock_db,
                UUID("00000000-0000-0000-0000-000000000099"),
                {
                    "subscription_id": str(UUID("00000000-0000-0000-0000-000000000001")),
                    "event": "experiment.winner_promoted",
                    "data": {},
                },
            )
