"""EVOLVE job handler.

Payload schema:
  experiment_id: str (UUID)
  deployment_id: str (UUID)
  winner_variant: str
  confidence: float
  current_challenger: str
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.loop.evolve.engine import (
    complete_deployment,
    promote_winner,
    start_next_challenger,
)

logger = logging.getLogger(__name__)


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

    started = await start_next_challenger(db, deployment_id, winner_variant, current_challenger)
    if not started:
        await complete_deployment(db, deployment_id, winner_variant)

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
