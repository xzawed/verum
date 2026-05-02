"""EVOLVE job handler.

Payload schema:
  experiment_id: str (UUID)
  deployment_id: str (UUID)
  winner_variant: str
  confidence: float
  current_challenger: str
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.loop.evolve.engine import (
    complete_deployment,
    promote_winner,
    start_next_challenger,
)

logger = logging.getLogger(__name__)


async def _enqueue_webhooks(
    db: AsyncSession,
    deployment_id: uuid.UUID,
    owner_user_id: uuid.UUID,
    event: str,
    data: dict[str, Any],
) -> None:
    """Query active subscriptions for this deployment+event and enqueue webhook jobs."""
    rows = (
        await db.execute(
            text(
                "SELECT id FROM webhook_subscriptions"
                " WHERE is_active = TRUE"
                " AND user_id = CAST(:uid AS uuid)"
                " AND (deployment_id = CAST(:dep_id AS uuid) OR deployment_id IS NULL)"
                " AND events @> CAST(:event_json AS jsonb)"
            ),
            {
                "uid": str(owner_user_id),
                "dep_id": str(deployment_id),
                "event_json": json.dumps([event]),
            },
        )
    ).mappings().all()

    for row in rows:
        webhook_payload = json.dumps({
            "subscription_id": str(row["id"]),
            "event": event,
            "data": data,
        })
        await db.execute(
            text(
                "INSERT INTO verum_jobs (kind, payload, status, owner_user_id)"
                " VALUES ("
                "  'webhook',"
                "  CAST(:payload AS jsonb),"
                "  'queued',"
                "  CAST(:uid AS uuid)"
                " )"
            ),
            {"payload": webhook_payload, "uid": str(owner_user_id)},
        )

    if rows:
        logger.info(
            "EVOLVE: enqueued %d webhook jobs for event=%s deployment=%s",
            len(rows),
            event,
            deployment_id,
        )


async def handle_evolve(
    db: AsyncSession,
    owner_user_id: uuid.UUID,
    payload: dict[str, Any],
) -> dict[str, Any]:
    experiment_id = uuid.UUID(payload["experiment_id"])
    deployment_id = uuid.UUID(payload["deployment_id"])
    winner_variant: str = payload["winner_variant"]
    confidence: float = float(payload["confidence"])
    current_challenger: str = payload["current_challenger"]

    await promote_winner(db, experiment_id, deployment_id, winner_variant, confidence)

    await _enqueue_webhooks(
        db,
        deployment_id,
        owner_user_id,
        "experiment.winner_promoted",
        {
            "deployment_id": str(deployment_id),
            "experiment_id": str(experiment_id),
            "winner_variant": winner_variant,
            "confidence": confidence,
        },
    )

    started = await start_next_challenger(db, deployment_id, winner_variant, current_challenger)
    if not started:
        await complete_deployment(db, deployment_id, winner_variant)
        await _enqueue_webhooks(
            db,
            deployment_id,
            owner_user_id,
            "experiment.completed",
            {
                "deployment_id": str(deployment_id),
                "experiment_id": str(experiment_id),
                "winner_variant": winner_variant,
                "confidence": confidence,
            },
        )

    logger.info(
        "EVOLVE job done: deployment=%s winner=%s next_started=%s",
        deployment_id,
        winner_variant,
        started,
    )
    return {
        "deployment_id": str(deployment_id),
        "winner_variant": winner_variant,
        "next_round_started": started,
    }
