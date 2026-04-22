"""DEPLOY job handler.

Payload schema:
  generation_id: str (UUID)
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.loop.deploy.repository import create_deployment

logger = logging.getLogger(__name__)


async def handle_deploy(
    db: AsyncSession,
    owner_user_id: uuid.UUID,
    payload: dict[str, Any],
) -> dict[str, Any]:
    generation_id = uuid.UUID(payload["generation_id"])
    deployment = await create_deployment(db, generation_id, variant_fraction=0.10)
    logger.info("DEPLOY complete: deployment_id=%s status=%s", deployment.deployment_id, deployment.status)
    return {
        "deployment_id": str(deployment.deployment_id),
        "status": deployment.status,
        "traffic_split": deployment.traffic_split,
    }
