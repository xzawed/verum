"""EVOLVE webhook delivery handler.

Payload schema:
  subscription_id: str (UUID)
  event: str  — "experiment.winner_promoted" | "experiment.completed"
  data: dict  — event-specific data
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def handle_webhook(
    db: AsyncSession,
    owner_user_id: uuid.UUID,
    payload: dict[str, Any],
) -> dict[str, Any]:
    subscription_id = uuid.UUID(payload["subscription_id"])
    event: str = payload["event"]
    data: dict[str, Any] = payload.get("data", {})

    row = (
        await db.execute(
            text(
                "SELECT url, signing_secret FROM webhook_subscriptions"
                " WHERE id = CAST(:id AS uuid) AND is_active = TRUE"
            ),
            {"id": str(subscription_id)},
        )
    ).mappings().first()

    if row is None:
        logger.warning("Webhook subscription %s not found or inactive", subscription_id)
        return {"skipped": "subscription not found or inactive"}

    body = json.dumps(
        {"event": event, "timestamp": datetime.now(tz=timezone.utc).isoformat(), **data},
        sort_keys=True,
    )
    sig = "sha256=" + hmac.new(
        row["signing_secret"].encode(),
        body.encode(),
        hashlib.sha256,
    ).hexdigest()

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            row["url"],
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Verum-Signature": sig,
                "X-Verum-Event": event,
            },
            timeout=10.0,
        )
        resp.raise_for_status()

    logger.info(
        "Webhook delivered: subscription=%s event=%s status=%d",
        subscription_id,
        event,
        resp.status_code,
    )
    return {"delivered": True, "status_code": resp.status_code}
