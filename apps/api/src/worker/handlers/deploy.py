"""DEPLOY job handler.

Payload schema:
  generation_id: str (UUID)
"""
from __future__ import annotations

import logging
import os
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.loop.deploy.orchestrator import deploy_and_start_experiment

logger = logging.getLogger(__name__)

_VARIANT_FRACTION: float = float(os.environ.get("VERUM_DEPLOY_VARIANT_FRACTION", "0.10"))
_TEST_MODE: bool = os.environ.get("VERUM_TEST_MODE", "") == "1"


async def handle_deploy(
    db: AsyncSession,
    owner_user_id: uuid.UUID,
    payload: dict[str, Any],
) -> dict[str, Any]:
    generation_id = uuid.UUID(payload["generation_id"])
    deployment, experiment_id = await deploy_and_start_experiment(
        db, generation_id, variant_fraction=_VARIANT_FRACTION
    )
    await db.commit()

    logger.info(
        "DEPLOY+EXPERIMENT: deployment_id=%s experiment_id=%s status=%s",
        deployment.deployment_id,
        experiment_id,
        deployment.status,
    )

    result: dict[str, Any] = {
        "deployment_id": str(deployment.deployment_id),
        "status": deployment.status,
        "traffic_split": deployment.traffic_split,
    }
    if _TEST_MODE:
        result["api_key"] = deployment.api_key
    return result
