"""Database I/O for the DEPLOY stage."""
from __future__ import annotations

import hashlib
import json
import secrets
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.loop.deploy.engine import compute_traffic_split
from src.loop.deploy.models import Deployment, DeploymentWithKey


async def create_deployment(
    db: AsyncSession,
    generation_id: uuid.UUID,
    variant_fraction: float = 0.10,
) -> DeploymentWithKey:
    """Create a new deployment and return it with a one-time raw API key.

    The raw token is returned in DeploymentWithKey.api_key and must be
    surfaced to the caller immediately — it is never stored in the DB.
    Only the sha256 hash is persisted in the api_key_hash column.

    Args:
        db: Async SQLAlchemy session.
        generation_id: UUID of the generation to deploy.
        variant_fraction: Fraction of traffic routed to the variant (0–1).

    Returns:
        DeploymentWithKey containing the deployment data and the raw api_key.
    """
    token = secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(token.encode()).hexdigest()

    split = compute_traffic_split(variant_fraction)
    row = (await db.execute(
        text(
            "INSERT INTO deployments (generation_id, status, traffic_split, api_key_hash)"
            " VALUES (:gid, 'canary', CAST(:split AS jsonb), :key_hash)"
            " RETURNING id, generation_id, status, traffic_split, error_count, total_calls, created_at, updated_at"
        ),
        {"gid": str(generation_id), "split": json.dumps(split), "key_hash": key_hash},
    )).mappings().first()
    await db.commit()
    if row is None:
        raise RuntimeError(f"create_deployment: INSERT returned no row for generation_id={generation_id}")
    deployment = _row_to_deployment(dict(row))
    return DeploymentWithKey(**deployment.model_dump(), api_key=token)


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
            "UPDATE deployments SET traffic_split = CAST(:split AS jsonb), updated_at = now()"
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
            "UPDATE deployments SET status = 'rolled_back', traffic_split = CAST(:split AS jsonb), updated_at = now()"
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
