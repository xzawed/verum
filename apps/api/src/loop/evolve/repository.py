"""Database I/O for the EVOLVE stage."""
from __future__ import annotations

import json
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def update_deployment_baseline(
    db: AsyncSession,
    deployment_id: uuid.UUID,
    new_baseline: str,
) -> None:
    await db.execute(
        text(
            "UPDATE deployments SET current_baseline_variant = :bv, updated_at = now()"
            " WHERE id = :did"
        ),
        {"bv": new_baseline, "did": str(deployment_id)},
    )
    await db.commit()


async def update_traffic_split(
    db: AsyncSession,
    deployment_id: uuid.UUID,
    split: dict[str, float],
) -> None:
    await db.execute(
        text(
            "UPDATE deployments SET traffic_split = :split::jsonb, updated_at = now()"
            " WHERE id = :did"
        ),
        {"split": json.dumps(split), "did": str(deployment_id)},
    )
    await db.commit()


async def set_experiment_status(
    db: AsyncSession,
    deployment_id: uuid.UUID,
    status: str,
) -> None:
    """Set deployments.experiment_status to 'running' | 'completed' | 'idle'."""
    await db.execute(
        text(
            "UPDATE deployments SET experiment_status = :s, updated_at = now()"
            " WHERE id = :did"
        ),
        {"s": status, "did": str(deployment_id)},
    )
    await db.commit()
