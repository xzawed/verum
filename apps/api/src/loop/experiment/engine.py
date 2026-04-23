"""Pure functions for Bayesian A/B experiment evaluation.

[7] EXPERIMENT stage of The Verum Loop.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# Challenger variants tried in this fixed order.
CHALLENGER_ORDER: list[str] = ["cot", "few_shot", "role_play", "concise"]

MIN_SAMPLES = 100
CONFIDENCE_THRESHOLD = 0.95
CONFIDENCE_FLOOR = 0.05


def compute_winner_score(
    judge_score: float,
    cost_usd: float,
    max_cost_in_window: float,
    cost_weight: float = 0.1,
) -> float:
    """Return composite score: judge_score − cost_weight × cost_normalized."""
    cost_normalized = cost_usd / max_cost_in_window if max_cost_in_window > 0 else 0.0
    return judge_score - cost_weight * cost_normalized


def bayesian_confidence(
    b_wins: int,
    b_n: int,
    c_wins: int,
    c_n: int,
    samples: int = 10_000,
) -> float:
    """Return P(challenger win_rate > baseline win_rate) via Monte Carlo sampling.

    Falls back to raw win-rate comparison if scipy is unavailable.
    """
    try:
        from scipy import stats  # type: ignore[import-untyped]

        rng = np.random.default_rng()
        baseline = stats.beta(1 + b_wins, 1 + (b_n - b_wins))
        challenger = stats.beta(1 + c_wins, 1 + (c_n - c_wins))
        return float(np.mean(challenger.rvs(samples, random_state=rng) > baseline.rvs(samples, random_state=rng)))
    except ImportError:
        logger.warning("scipy not available; falling back to raw win-rate comparison")
        b_rate = b_wins / b_n if b_n > 0 else 0.0
        c_rate = c_wins / c_n if c_n > 0 else 0.0
        return 1.0 if c_rate > b_rate else 0.0


def check_experiment(
    experiment_row: dict[str, Any],
    max_cost_in_window: float,
) -> "ExperimentResult":
    """Evaluate an experiment row and return an ExperimentResult.

    Does NOT write to the database.
    """
    from src.loop.experiment.models import ExperimentResult, VariantStats

    b_wins: int = experiment_row["baseline_wins"]
    b_n: int = experiment_row["baseline_n"]
    c_wins: int = experiment_row["challenger_wins"]
    c_n: int = experiment_row["challenger_n"]

    conf = bayesian_confidence(b_wins, b_n, c_wins, c_n)

    converged = (
        b_n >= MIN_SAMPLES
        and c_n >= MIN_SAMPLES
        and (conf >= CONFIDENCE_THRESHOLD or conf <= CONFIDENCE_FLOOR)
    )

    if converged:
        winner = (
            experiment_row["challenger_variant"]
            if conf >= CONFIDENCE_THRESHOLD
            else experiment_row["baseline_variant"]
        )
    else:
        winner = None

    return ExperimentResult(
        experiment_id=uuid.UUID(str(experiment_row["id"])),
        deployment_id=uuid.UUID(str(experiment_row["deployment_id"])),
        baseline=VariantStats(
            variant=experiment_row["baseline_variant"],
            wins=b_wins,
            n=b_n,
            avg_winner_score=0.0,
        ),
        challenger=VariantStats(
            variant=experiment_row["challenger_variant"],
            wins=c_wins,
            n=c_n,
            avg_winner_score=0.0,
        ),
        confidence=conf,
        converged=converged,
        winner_variant=winner,
    )
