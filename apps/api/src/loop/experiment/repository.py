"""Database I/O for the EXPERIMENT stage."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.helpers import execute_commit


async def get_running_experiment(
    db: AsyncSession,
    deployment_id: uuid.UUID,
) -> dict[str, Any] | None:
    """Return the currently running experiment row for a deployment, or None."""
    row = (
        await db.execute(
            text(
                "SELECT id, deployment_id, baseline_variant, challenger_variant,"
                " status, winner_variant, confidence,"
                " baseline_wins, baseline_n, challenger_wins, challenger_n,"
                " win_threshold, started_at"
                " FROM experiments"
                " WHERE deployment_id = :did AND status = 'running'"
                " ORDER BY started_at DESC LIMIT 1"
            ),
            {"did": str(deployment_id)},
        )
    ).mappings().first()
    return dict(row) if row else None


async def get_all_running_experiments(db: AsyncSession) -> list[dict[str, Any]]:
    """Return all running experiment rows across all deployments."""
    rows = (
        await db.execute(
            text(
                "SELECT e.id, e.deployment_id, e.baseline_variant, e.challenger_variant,"
                " e.status, e.winner_variant, e.confidence,"
                " e.baseline_wins, e.baseline_n, e.challenger_wins, e.challenger_n,"
                " e.win_threshold, e.started_at"
                " FROM experiments e"
                " JOIN deployments d ON d.id = e.deployment_id"
                " WHERE e.status = 'running' AND d.experiment_status = 'running'"
            )
        )
    ).mappings().all()
    return [dict(r) for r in rows]


async def update_experiment_stats(
    db: AsyncSession,
    experiment_id: uuid.UUID,
    baseline_wins: int,
    baseline_n: int,
    challenger_wins: int,
    challenger_n: int,
) -> None:
    """Overwrite win counters with freshly aggregated values."""
    await execute_commit(
        db,
        text(
            "UPDATE experiments"
            " SET baseline_wins = :bw, baseline_n = :bn,"
            "     challenger_wins = :cw, challenger_n = :cn"
            " WHERE id = :eid"
        ),
        {
            "bw": baseline_wins,
            "bn": baseline_n,
            "cw": challenger_wins,
            "cn": challenger_n,
            "eid": str(experiment_id),
        },
    )


async def aggregate_variant_wins(
    db: AsyncSession,
    deployment_id: uuid.UUID,
    baseline_variant: str,
    challenger_variant: str,
    win_threshold: float,
) -> tuple[int, int, int, int, int]:
    """Count binary wins (winner_score > win_threshold) per variant.

    winner_score = judge_score - 0.1 * (cost_usd / max_cost_in_window).
    Traces with NULL judge_score are excluded.

    Returns (baseline_wins, baseline_n, challenger_wins, challenger_n, null_score_count).
    """
    max_cost_row = (
        await db.execute(
            text(
                "SELECT COALESCE(MAX(trace_cost.total_cost), 0) AS max_cost"
                " FROM traces t"
                " LEFT JOIN ("
                "   SELECT trace_id, SUM(cost_usd) AS total_cost"
                "   FROM spans"
                "   WHERE started_at >= now() - interval '7 days'"
                "   GROUP BY trace_id"
                " ) trace_cost ON trace_cost.trace_id = t.id"
                " WHERE t.deployment_id = :did AND t.created_at >= now() - interval '7 days'"
            ),
            {"did": str(deployment_id)},
        )
    ).mappings().first()
    max_cost = float(max_cost_row["max_cost"]) if max_cost_row else 0.0

    rows = (
        await db.execute(
            text(
                "SELECT t.variant,"
                "  COUNT(*) FILTER (WHERE t.judge_score IS NOT NULL) AS n,"
                "  COUNT(*) FILTER ("
                "    WHERE t.judge_score IS NOT NULL"
                "    AND ("
                "      t.judge_score - 0.1 * CASE WHEN :max_cost > 0"
                "        THEN COALESCE(trace_cost.total_cost, 0)::float / :max_cost ELSE 0 END"
                "    ) > :threshold"
                "  ) AS wins,"
                "  COUNT(*) FILTER (WHERE t.judge_score IS NULL) AS null_score_count"
                " FROM traces t"
                " LEFT JOIN ("
                "   SELECT trace_id, SUM(cost_usd) AS total_cost"
                "   FROM spans"
                "   GROUP BY trace_id"
                " ) trace_cost ON trace_cost.trace_id = t.id"
                " WHERE t.deployment_id = :did"
                "   AND t.variant IN (:bv, :cv)"
                " GROUP BY t.variant"
            ),
            {
                "did": str(deployment_id),
                "bv": baseline_variant,
                "cv": challenger_variant,
                "max_cost": max_cost,
                "threshold": win_threshold,
            },
        )
    ).mappings().all()

    stats: dict[str, dict[str, int]] = {
        baseline_variant: {"wins": 0, "n": 0, "null_count": 0},
        challenger_variant: {"wins": 0, "n": 0, "null_count": 0},
    }
    for row in rows:
        if row["variant"] in stats:
            stats[row["variant"]] = {
                "wins": int(row["wins"]),
                "n": int(row["n"]),
                "null_count": int(row["null_score_count"]),
            }

    null_total = sum(s["null_count"] for s in stats.values())
    return (
        stats[baseline_variant]["wins"],
        stats[baseline_variant]["n"],
        stats[challenger_variant]["wins"],
        stats[challenger_variant]["n"],
        null_total,
    )


async def insert_experiment(
    db: AsyncSession,
    deployment_id: uuid.UUID,
    baseline_variant: str,
    challenger_variant: str,
) -> dict[str, Any]:
    """Insert a new running experiment and return the row."""
    row = (
        await db.execute(
            text(
                "INSERT INTO experiments (deployment_id, baseline_variant, challenger_variant, status)"
                " VALUES (:did, :bv, :cv, 'running')"
                " RETURNING *"
            ),
            {"did": str(deployment_id), "bv": baseline_variant, "cv": challenger_variant},
        )
    ).mappings().first()
    await db.commit()
    if row is None:
        raise RuntimeError(
            f"insert_experiment: INSERT returned no row for deployment_id={deployment_id}"
        )
    return dict(row)


async def mark_experiment_converged(
    db: AsyncSession,
    experiment_id: uuid.UUID,
    winner_variant: str,
    confidence: float,
) -> None:
    await execute_commit(
        db,
        text(
            "UPDATE experiments"
            " SET status = 'converged', winner_variant = :wv, confidence = :conf,"
            "     converged_at = now()"
            " WHERE id = :eid"
        ),
        {"wv": winner_variant, "conf": confidence, "eid": str(experiment_id)},
    )
