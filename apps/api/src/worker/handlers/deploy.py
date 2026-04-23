"""DEPLOY job handler.

Payload schema:
  generation_id: str (UUID)
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.loop.deploy.repository import create_deployment
from src.loop.evolve.repository import update_traffic_split
from src.loop.experiment.repository import insert_experiment

logger = logging.getLogger(__name__)


async def handle_deploy(
    db: AsyncSession,
    owner_user_id: uuid.UUID,
    payload: dict[str, Any],
) -> dict[str, Any]:
    generation_id = uuid.UUID(payload["generation_id"])
    deployment = await create_deployment(db, generation_id, variant_fraction=0.10)
    logger.info("DEPLOY complete: deployment_id=%s status=%s", deployment.deployment_id, deployment.status)

    # Start experiment tracking: set deployment status and insert round 1
    await db.execute(
        text(
            "UPDATE deployments SET experiment_status = 'running', updated_at = now()"
            " WHERE id = :did"
        ),
        {"did": str(deployment.deployment_id)},
    )
    await db.commit()

    await update_traffic_split(db, deployment.deployment_id, {"original": 0.9, "cot": 0.1})
    await insert_experiment(db, deployment.deployment_id, "original", "cot")
    logger.info(
        "EXPERIMENT: round 1 started (original vs cot) for deployment %s",
        deployment.deployment_id,
    )

    return {
        "deployment_id": str(deployment.deployment_id),
        "status": deployment.status,
        "traffic_split": deployment.traffic_split,
    }
