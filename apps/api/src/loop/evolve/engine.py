"""Orchestration logic for the EVOLVE stage ([8] of The Verum Loop)."""
from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.loop.evolve.repository import (
    set_experiment_status,
    update_deployment_baseline,
    update_traffic_split,
)
from src.loop.experiment.engine import CHALLENGER_ORDER
from src.loop.experiment.repository import insert_experiment, mark_experiment_converged

logger = logging.getLogger(__name__)


async def promote_winner(
    db: AsyncSession,
    experiment_id: uuid.UUID,
    deployment_id: uuid.UUID,
    winner_variant: str,
    confidence: float,
) -> None:
    """Record convergence on the experiment row and update deployment baseline."""
    await mark_experiment_converged(db, experiment_id, winner_variant, confidence)
    await update_deployment_baseline(db, deployment_id, winner_variant)
    logger.info(
        "EVOLVE: experiment %s converged — winner=%s confidence=%.3f",
        experiment_id,
        winner_variant,
        confidence,
    )


def next_challenger(current_baseline: str, current_challenger: str) -> str | None:
    """Return the next challenger variant after the current round, or None if all done."""
    try:
        current_idx = CHALLENGER_ORDER.index(current_challenger)
    except ValueError:
        return None
    next_idx = current_idx + 1
    if next_idx >= len(CHALLENGER_ORDER):
        return None
    return CHALLENGER_ORDER[next_idx]


async def start_next_challenger(
    db: AsyncSession,
    deployment_id: uuid.UUID,
    winner_variant: str,
    current_challenger: str,
) -> bool:
    """Insert next experiment round and update traffic split.

    Returns True if a new round started, False if all rounds are done.
    """
    challenger = next_challenger(winner_variant, current_challenger)
    if challenger is None:
        return False

    await insert_experiment(db, deployment_id, winner_variant, challenger)
    await update_traffic_split(db, deployment_id, {winner_variant: 0.9, challenger: 0.1})
    logger.info(
        "EVOLVE: deployment %s — new experiment %s vs %s",
        deployment_id,
        winner_variant,
        challenger,
    )
    return True


async def complete_deployment(
    db: AsyncSession,
    deployment_id: uuid.UUID,
    winner_variant: str,
) -> None:
    """Final round complete: 100% traffic to winner, mark deployment completed."""
    await update_traffic_split(db, deployment_id, {winner_variant: 1.0})
    await set_experiment_status(db, deployment_id, "completed")
    logger.info(
        "EVOLVE: deployment %s complete — final winner=%s at 100%%",
        deployment_id,
        winner_variant,
    )
