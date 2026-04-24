"""Email notifications for Verum via aiosmtplib.

Real delivery requires SMTP_HOST to be set (see config.py).
When SMTP_HOST is empty the functions log to console and return — no send.
"""
from __future__ import annotations

import logging
from email.message import EmailMessage

import src.config as cfg

logger = logging.getLogger(__name__)

VERUM_EMAIL = cfg.SMTP_FROM


async def _send(subject: str, body: str, to: str) -> None:
    """Send a plain-text email. No-op (log only) when SMTP_HOST is unset."""
    if not cfg.SMTP_HOST:
        logger.info("[EMAIL no-op] To=%s | Subject=%s", to, subject)
        return

    import aiosmtplib  # soft import — not needed when SMTP_HOST is unset

    msg = EmailMessage()
    msg["From"] = cfg.SMTP_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        await aiosmtplib.send(
            msg,
            hostname=cfg.SMTP_HOST,
            port=cfg.SMTP_PORT,
            username=cfg.SMTP_USER or None,
            password=cfg.SMTP_PASSWORD or None,
            use_tls=cfg.SMTP_USE_TLS,
        )
        logger.debug("Email sent: To=%s Subject=%s", to, subject)
    except aiosmtplib.SMTPException as exc:
        logger.error("Failed to send email to %s: %s", to, exc)


async def send_welcome_email(user_email: str, github_login: str) -> None:
    """Send welcome email when a user connects their first repo."""
    subject = "Welcome to Verum — your AI just got smarter"
    body = (
        f"Hi {github_login},\n\n"
        "Your first repository is connected. Verum will now analyze your LLM call patterns\n"
        "and start building prompts, RAG indexes, and evaluation sets automatically.\n\n"
        "You'll receive another email once the first analysis cycle completes.\n\n"
        "— The Verum Loop\n"
        "https://verum.dev\n"
    )
    await _send(subject, body, user_email)


async def send_quota_warning_email(
    user_email: str, resource: str, pct_used: float
) -> None:
    """Send quota warning at 80% usage."""
    pct_str = f"{pct_used * 100:.0f}%"
    subject = f"Verum: {resource} at {pct_str} of your free limit"
    body = (
        f"Hi,\n\n"
        f"Your Verum account has used {pct_str} of the free-tier {resource} limit.\n"
        "Once the limit is reached, new ingestion jobs will pause until the quota resets.\n\n"
        "To keep the Verum Loop running continuously, consider self-hosting or "
        "reaching out at https://verum.dev.\n\n"
        "— The Verum Loop\n"
    )
    await _send(subject, body, user_email)


async def send_quota_exceeded_email(user_email: str, resource: str) -> None:
    """Send quota exceeded notice."""
    subject = f"Verum: {resource} limit reached on your free account"
    body = (
        f"Hi,\n\n"
        f"Your Verum account has reached the free-tier {resource} limit.\n"
        "New jobs for this resource are paused.\n\n"
        "To continue without limits, self-host Verum (MIT license) or contact "
        "us at https://verum.dev.\n\n"
        "— The Verum Loop\n"
    )
    await _send(subject, body, user_email)
