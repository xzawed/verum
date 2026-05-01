"""Tests for src/loop/email.py."""
from __future__ import annotations

import importlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import src.config as cfg
from src.loop.email import (
    send_generate_complete_email,
    send_quota_exceeded_email,
    send_quota_warning_email,
    send_welcome_email,
)


# ── No-op path (SMTP_HOST unset) ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_no_send_when_smtp_host_empty(caplog):
    with patch.object(cfg, "SMTP_HOST", ""):
        import logging
        with caplog.at_level(logging.INFO, logger="src.loop.email"):
            await send_welcome_email("user@example.com", "alice")
    assert "no-op" in caplog.text or "EMAIL" in caplog.text
    # aiosmtplib.send must NOT have been called
    # (if it were, it would fail because SMTP_HOST is empty)


@pytest.mark.asyncio
async def test_quota_warning_no_op_logs(caplog):
    with patch.object(cfg, "SMTP_HOST", ""):
        import logging
        with caplog.at_level(logging.INFO, logger="src.loop.email"):
            await send_quota_warning_email("user@example.com", "chunks", 0.85)
    assert "no-op" in caplog.text or "EMAIL" in caplog.text


@pytest.mark.asyncio
async def test_quota_exceeded_no_op_logs(caplog):
    with patch.object(cfg, "SMTP_HOST", ""):
        import logging
        with caplog.at_level(logging.INFO, logger="src.loop.email"):
            await send_quota_exceeded_email("user@example.com", "traces")
    assert "no-op" in caplog.text or "EMAIL" in caplog.text


# ── Real send path (SMTP_HOST configured) ─────────────────────────────────────

@pytest.mark.asyncio
async def test_welcome_email_calls_aiosmtplib():
    mock_send = AsyncMock()
    with (
        patch.object(cfg, "SMTP_HOST", "smtp.example.com"),
        patch.object(cfg, "SMTP_PORT", 587),
        patch.object(cfg, "SMTP_FROM", "noreply@verum.dev"),
        patch.object(cfg, "SMTP_USER", "user"),
        patch.object(cfg, "SMTP_PASSWORD", "pass"),
        patch.object(cfg, "SMTP_USE_TLS", True),
        patch("aiosmtplib.send", mock_send),
    ):
        await send_welcome_email("alice@example.com", "alice")

    mock_send.assert_awaited_once()
    msg = mock_send.call_args[0][0]
    assert msg["To"] == "alice@example.com"
    assert "Welcome" in msg["Subject"]
    assert "alice" in msg.get_body().get_content()


@pytest.mark.asyncio
async def test_quota_warning_email_content():
    mock_send = AsyncMock()
    with (
        patch.object(cfg, "SMTP_HOST", "smtp.example.com"),
        patch("aiosmtplib.send", mock_send),
    ):
        await send_quota_warning_email("bob@example.com", "chunks", 0.82)

    msg = mock_send.call_args[0][0]
    assert msg["To"] == "bob@example.com"
    assert "82%" in msg["Subject"]
    assert "chunks" in msg["Subject"]
    body = msg.get_body().get_content()
    assert "82%" in body
    assert "chunks" in body


@pytest.mark.asyncio
async def test_quota_exceeded_email_content():
    mock_send = AsyncMock()
    with (
        patch.object(cfg, "SMTP_HOST", "smtp.example.com"),
        patch("aiosmtplib.send", mock_send),
    ):
        await send_quota_exceeded_email("carol@example.com", "repos")

    msg = mock_send.call_args[0][0]
    assert msg["To"] == "carol@example.com"
    assert "repos" in msg["Subject"]
    body = msg.get_body().get_content()
    assert "repos" in body


@pytest.mark.asyncio
async def test_generate_complete_email_content():
    mock_send = AsyncMock()
    with (
        patch.object(cfg, "SMTP_HOST", "smtp.example.com"),
        patch("aiosmtplib.send", mock_send),
    ):
        await send_generate_complete_email(
            "eve@example.com", "tarot_divination", "https://github.com/owner/repo"
        )

    mock_send.assert_awaited_once()
    msg = mock_send.call_args[0][0]
    assert msg["To"] == "eve@example.com"
    assert "ready" in msg["Subject"]
    body = msg.get_body().get_content()
    assert "tarot_divination" in body
    assert "https://github.com/owner/repo" in body


# ── SMTP failure is logged, not raised ───────────────────────────────────────

@pytest.mark.asyncio
async def test_smtp_error_is_logged_not_raised(caplog):
    import aiosmtplib

    mock_send = AsyncMock(side_effect=aiosmtplib.SMTPException("connection refused"))
    with (
        patch.object(cfg, "SMTP_HOST", "smtp.example.com"),
        patch("aiosmtplib.send", mock_send),
    ):
        import logging
        with caplog.at_level(logging.ERROR, logger="src.loop.email"):
            await send_welcome_email("dave@example.com", "dave")

    assert "Failed to send email" in caplog.text
