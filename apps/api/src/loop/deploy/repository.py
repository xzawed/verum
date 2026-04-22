"""Database I/O for the DEPLOY stage."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.loop.deploy.engine import compute_traffic_split
from src.loop.deploy.models import Deployment


async def create_deployment(
    db: AsyncSession,
    generation_id: uuid.UUID,
    variant_fraction: float = 0.10,
) -> Deployment:
    split = compute_traffic_split(variant_fraction)
    row = (await db.execute(
        text(
            "INSERT INTO deployments (generation_id, status, traffic_split)"
            " VALUES (:gid, 'canary', :split::jsonb)"
            " RETURNING id, generation_id, status, traffic_split, error_count, total_calls, created_at, updated_at"
        ),
        {"gid": str(generation_id), "split": json.dumps(split)},
    )).mappings().first()
    await db.commit()
    if row is None:
        raise RuntimeError(f"create_deployment: INSERT returned no row for generation_id={generation_id}")
    return _row_to_deployment(dict(row))


async def get_deployment(db: AsyncSession, deployment_id: uuid.UUID) -> Deployment | None:
    row = (await db.execute(
        text("SELECT * FROM deployments WHERE id = :id"),
        {"id": str(deployment_id)},
    )).mappings().first()
    return _row_to_deployment(dict(row)) if row else None


async def update_traffic(
    db: AsyncSession,
    deployment_id: uuid.UUID,
    variant_fraction: float,
) -> Deployment | None:
    split = compute_traffic_split(variant_fraction)
    row = (await db.execute(
        text(
            "UPDATE deployments SET traffic_split = :split::jsonb, updated_at = now()"
            " WHERE id = :id RETURNING *"
        ),
        {"split": json.dumps(split), "id": str(deployment_id)},
    )).mappings().first()
    await db.commit()
    return _row_to_deployment(dict(row)) if row else None


async def rollback_deployment(db: AsyncSession, deployment_id: uuid.UUID) -> Deployment | None:
    split = json.dumps({"baseline": 1.0, "variant": 0.0})
    row = (await db.execute(
        text(
            "UPDATE deployments SET status = 'rolled_back', traffic_split = :split::jsonb, updated_at = now()"
            " WHERE id = :id RETURNING *"
        ),
        {"split": split, "id": str(deployment_id)},
    )).mappings().first()
    await db.commit()
    return _row_to_deployment(dict(row)) if row else None


async def get_variant_prompt(db: AsyncSession, deployment_id: uuid.UUID) -> str | None:
    """Return the CoT variant prompt content for SDK config endpoint."""
    row = (await db.execute(
        text(
            "SELECT pv.content FROM deployments d"
            " JOIN generations g ON g.id = d.generation_id"
            " JOIN prompt_variants pv ON pv.generation_id = g.id"
            " WHERE d.id = :did AND pv.variant_type = 'cot'"
            " LIMIT 1"
        ),
        {"did": str(deployment_id)},
    )).mappings().first()
    return row["content"] if row else None


def _row_to_deployment(row: dict) -> Deployment:  # type: ignore[type-arg]
    split = row["traffic_split"]
    if isinstance(split, str):
        split = json.loads(split)
    return Deployment(
        deployment_id=uuid.UUID(str(row["id"])),
        generation_id=uuid.UUID(str(row["generation_id"])),
        status=row["status"],
        traffic_split=split,
        error_count=row["error_count"],
        total_calls=row["total_calls"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
