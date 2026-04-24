"""Deploy orchestrator — creates deployment and inserts round-1 experiment atomically."""
from __future__ import annotations

import hashlib
import json
import secrets
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.loop.deploy.engine import compute_traffic_split
from src.loop.deploy.models import DeploymentWithKey


async def deploy_and_start_experiment(
    db: AsyncSession,
    generation_id: uuid.UUID,
    variant_fraction: float = 0.10,
) -> tuple[DeploymentWithKey, uuid.UUID]:
    """Create a deployment and insert round-1 experiment row without committing.

    Returns (DeploymentWithKey, experiment_id). Caller owns db.commit().

    Args:
        db: Active async SQLAlchemy session.
        generation_id: UUID of the generation to deploy.
        variant_fraction: Fraction of traffic routed to the variant (0–1).

    Returns:
        Tuple of (DeploymentWithKey, experiment_id UUID).

    Raises:
        RuntimeError: If the INSERT returns no row.
    """
    token = secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(token.encode()).hexdigest()
    split = compute_traffic_split(variant_fraction)

    dep_row = (await db.execute(
        text(
            "INSERT INTO deployments"
            " (generation_id, status, traffic_split, api_key_hash, experiment_status)"
            " VALUES (:gid, 'canary', CAST(:split AS jsonb), :key_hash, 'running')"
            " RETURNING id, generation_id, status, traffic_split, error_count,"
            "   total_calls, created_at, updated_at"
        ),
        {"gid": str(generation_id), "split": json.dumps(split), "key_hash": key_hash},
    )).mappings().first()

    if dep_row is None:
        raise RuntimeError(
            f"deploy_and_start_experiment: deployment INSERT returned no row "
            f"for generation_id={generation_id}"
        )

    deployment_id = uuid.UUID(str(dep_row["id"]))

    exp_row = (await db.execute(
        text(
            "INSERT INTO experiments"
            " (deployment_id, baseline_variant, challenger_variant, status)"
            " VALUES (:did, 'original', 'cot', 'running')"
            " RETURNING id"
        ),
        {"did": str(deployment_id)},
    )).mappings().first()

    if exp_row is None:
        raise RuntimeError(
            f"deploy_and_start_experiment: experiment INSERT returned no row "
            f"for deployment_id={deployment_id}"
        )

    experiment_id = uuid.UUID(str(exp_row["id"]))

    split_val = dep_row["traffic_split"]
    if isinstance(split_val, str):
        split_val = json.loads(split_val)

    deployment = DeploymentWithKey(
        deployment_id=deployment_id,
        generation_id=uuid.UUID(str(dep_row["generation_id"])),
        status=str(dep_row["status"]),
        traffic_split=split_val,
        error_count=int(dep_row["error_count"]),
        total_calls=int(dep_row["total_calls"]),
        created_at=dep_row["created_at"],
        updated_at=dep_row["updated_at"],
        api_key=token,
    )

    return deployment, experiment_id
