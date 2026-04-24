"""Database I/O for the OBSERVE stage."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.helpers import execute_commit
from src.loop.observe.models import DailyMetric, TraceRecord

_logger = logging.getLogger(__name__)


def calculate_cost(
    input_tokens: int,
    output_tokens: int,
    pricing: dict[str, float] | None,
) -> float | None:
    """Calculate USD cost from token counts and pricing row.

    Args:
        input_tokens: Number of input tokens consumed.
        output_tokens: Number of output tokens generated.
        pricing: Dict with keys ``input_per_1m_usd`` and ``output_per_1m_usd``,
            or ``None`` if the model is not in the pricing table.

    Returns:
        Cost in USD rounded to 6 decimal places, or None if pricing is missing.
    """
    if pricing is None:
        return None
    input_cost = (input_tokens / 1_000_000) * pricing["input_per_1m_usd"]
    output_cost = (output_tokens / 1_000_000) * pricing["output_per_1m_usd"]
    return round(input_cost + output_cost, 6)


async def _get_pricing(db: AsyncSession, model: str) -> dict[str, float] | None:
    """Fetch model pricing row. Returns None if model not in table."""
    row = (
        await db.execute(
            text(
                "SELECT input_per_1m_usd, output_per_1m_usd"
                " FROM model_pricing WHERE model_name = :model"
                " ORDER BY effective_from DESC LIMIT 1"
            ),
            {"model": model},
        )
    ).mappings().first()
    if row is None:
        _logger.warning(
            "model_pricing: no pricing found for model=%s, cost_usd will be NULL", model
        )
        return None
    return dict(row)


async def insert_trace(
    db: AsyncSession,
    record: TraceRecord,
) -> uuid.UUID:
    """Insert trace + span atomically. Returns the new trace_id.

    This is the primary write path for the OBSERVE stage [6].

    Args:
        db: Active async SQLAlchemy session.
        record: Structured trace data from an LLM call.

    Returns:
        UUID of the newly created trace row.
    """
    pricing = await _get_pricing(db, record.model)
    cost_usd = calculate_cost(record.input_tokens, record.output_tokens, pricing)

    trace_id = uuid.uuid4()
    span_id = uuid.uuid4()
    now = datetime.now(tz=timezone.utc)

    await db.execute(
        text(
            "INSERT INTO traces (id, deployment_id, variant, created_at)"
            " VALUES (:id, :dep, :variant, :now)"
        ),
        {
            "id": str(trace_id),
            "dep": str(record.deployment_id),
            "variant": record.variant,
            "now": now,
        },
    )
    await db.execute(
        text(
            "INSERT INTO spans (id, trace_id, model, input_tokens, output_tokens,"
            " latency_ms, cost_usd, error, started_at)"
            " VALUES (:id, :tid, :model, :inp, :out, :lat, :cost, :err, :now)"
        ),
        {
            "id": str(span_id),
            "tid": str(trace_id),
            "model": record.model,
            "inp": record.input_tokens,
            "out": record.output_tokens,
            "lat": record.latency_ms,
            "cost": cost_usd,
            "err": record.error,
            "now": now,
        },
    )
    await db.commit()
    return trace_id


async def update_judge_score(
    db: AsyncSession,
    trace_id: uuid.UUID,
    score: float,
    prompt_sent: str,
    raw_response: str,
) -> None:
    """Write judge score to traces and full prompt to judge_prompts.

    Args:
        db: Active async SQLAlchemy session.
        trace_id: UUID of the trace to score.
        score: LLM-as-Judge score (typically 0.0–1.0).
        prompt_sent: Full prompt string that was sent to the judge model.
        raw_response: Raw text response from the judge model.
    """
    now = datetime.now(tz=timezone.utc)
    await db.execute(
        text("UPDATE traces SET judge_score = :score WHERE id = :id"),
        {"score": score, "id": str(trace_id)},
    )
    await db.execute(
        text(
            "INSERT INTO judge_prompts (trace_id, prompt_sent, raw_response, judged_at)"
            " VALUES (:tid, :prompt, :resp, :now)"
            " ON CONFLICT (trace_id) DO UPDATE"
            " SET prompt_sent = EXCLUDED.prompt_sent,"
            "     raw_response = EXCLUDED.raw_response,"
            "     judged_at = EXCLUDED.judged_at"
        ),
        {"tid": str(trace_id), "prompt": prompt_sent, "resp": raw_response, "now": now},
    )
    await db.commit()


async def update_user_feedback(
    db: AsyncSession,
    trace_id: uuid.UUID,
    score: int,
) -> bool:
    """Set user_feedback (-1 or 1). Returns False if trace not found.

    Args:
        db: Active async SQLAlchemy session.
        trace_id: UUID of the trace receiving feedback.
        score: +1 for thumbs-up, -1 for thumbs-down.

    Returns:
        True if the row was updated, False if trace_id was not found.
    """
    result = await execute_commit(
        db,
        text("UPDATE traces SET user_feedback = :score WHERE id = :id RETURNING id"),
        {"score": score, "id": str(trace_id)},
    )
    return result.rowcount == 1  # type: ignore[attr-defined]


async def get_daily_metrics(
    db: AsyncSession,
    deployment_id: uuid.UUID,
    days: int = 7,
) -> list[DailyMetric]:
    """Return one DailyMetric per calendar day for the past N days.

    Args:
        db: Active async SQLAlchemy session.
        deployment_id: Filter traces to this deployment.
        days: How many calendar days to look back. Defaults to 7.

    Returns:
        List of DailyMetric ordered by date ascending.
    """
    rows = (
        await db.execute(
            text(
                "SELECT"
                "  DATE(t.created_at AT TIME ZONE 'UTC') AS date,"
                "  COALESCE(SUM(s.cost_usd), 0)::float AS total_cost_usd,"
                "  COUNT(t.id)::int AS call_count,"
                "  COALESCE(PERCENTILE_CONT(0.95) WITHIN GROUP"
                "    (ORDER BY s.latency_ms), 0)::int AS p95_latency_ms,"
                "  AVG(t.judge_score)::float AS avg_judge_score"
                " FROM traces t"
                " JOIN spans s ON s.trace_id = t.id"
                " WHERE t.deployment_id = :dep"
                "   AND t.created_at >= NOW() - (INTERVAL '1 day' * :days)"
                " GROUP BY DATE(t.created_at AT TIME ZONE 'UTC')"
                " ORDER BY date ASC"
            ),
            {"dep": str(deployment_id), "days": days},
        )
    ).mappings().all()

    return [
        DailyMetric(
            date=str(row["date"]),
            total_cost_usd=float(row["total_cost_usd"] or 0),
            call_count=int(row["call_count"]),
            p95_latency_ms=int(row["p95_latency_ms"] or 0),
            avg_judge_score=float(row["avg_judge_score"]) if row["avg_judge_score"] else None,
        )
        for row in rows
    ]
