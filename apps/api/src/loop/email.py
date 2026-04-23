"""Email notification stubs for Verum freemium tier.

Real SMTP integration is deferred. These functions log to console and
can be replaced with an HTTP call to Resend/Postmark when credentials
are configured.
"""
from __future__ import annotations
import logging

logger = logging.getLogger(__name__)

VERUM_EMAIL = "noreply@verum.dev"


def send_welcome_email(user_email: str, github_login: str) -> None:
    """Send welcome email when a user connects their first repo."""
    logger.info(
        "[EMAIL STUB] Welcome email → %s (user: %s). "
        "Configure SMTP_URL env var to enable real delivery.",
        user_email,
        github_login,
    )


def send_quota_warning_email(user_email: str, resource: str, pct_used: float) -> None:
    """Send quota warning at 80% usage."""
    logger.warning(
        "[EMAIL STUB] Quota warning → %s: %s at %.0f%% of free limit.",
        user_email,
        resource,
        pct_used * 100,
    )


def send_quota_exceeded_email(user_email: str, resource: str) -> None:
    """Send quota exceeded notice."""
    logger.error(
        "[EMAIL STUB] Quota exceeded → %s: %s limit reached. Upgrade to continue.",
        user_email,
        resource,
    )
