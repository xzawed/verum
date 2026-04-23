"""JUDGE job handler — LLM-as-Judge quality scoring.

Payload schema:
  trace_id: str (UUID)
  deployment_id: str (UUID)
  variant: str
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any

import anthropic
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.traces import Trace
from src.loop.observe.repository import update_judge_score

logger = logging.getLogger(__name__)

_judge_parse_failures = 0

_JUDGE_MODEL = "claude-sonnet-4-6"


def _build_judge_prompt(
    domain: str,
    tone: str,
    eval_pairs: list[dict[str, Any]],
) -> str:
    examples = "\n".join(
        f"  Q: {p['query']}\n  A: {p['expected_answer']}"
        for p in eval_pairs[:3]
    )
    return (
        "You are evaluating an AI assistant response for quality.\n"
        "Score from 0.0 to 1.0 based on: domain appropriateness, completeness,\n"
        "and alignment with the expected answer direction.\n\n"
        f"Domain: {domain} | Tone: {tone}\n\n"
        "Reference examples from this domain:\n"
        f"{examples}\n\n"
        'Respond ONLY with JSON: {"score": 0.0-1.0, "reason": "one sentence"}'
    )


def _parse_judge_response(raw: str) -> tuple[float | None, str | None]:
    """Parse Claude's JSON response. Returns (score, reason) or (None, None) on failure."""
    try:
        data = json.loads(raw)
        score = float(data["score"])
        score = max(0.0, min(1.0, score))  # clamp to [0, 1]
        reason = str(data.get("reason", ""))
        return score, reason
    except Exception:
        return None, None


async def handle_judge(
    db: AsyncSession,
    owner_user_id: uuid.UUID,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Run LLM-as-Judge scoring for a completed trace.

    This is part of step [6] OBSERVE in The Verum Loop. It asynchronously
    evaluates trace quality using Claude as a judge, storing the score back
    to the traces table for use in EXPERIMENT/EVOLVE stages.

    Args:
        db: Async database session.
        owner_user_id: The user who owns the deployment being judged.
        payload: Job payload with trace_id, deployment_id, and variant.

    Returns:
        Dict with trace_id, judge_score, and optional reason.

    Raises:
        ValueError: If the trace_id is not found in the database.
    """
    trace_id = uuid.UUID(payload["trace_id"])
    deployment_id = uuid.UUID(payload["deployment_id"])

    # Idempotency: skip if already scored
    trace = (
        await db.execute(select(Trace).where(Trace.id == trace_id))
    ).scalar_one_or_none()
    if trace is None:
        raise ValueError(f"Trace {trace_id} not found")
    if trace.judge_score is not None:
        logger.info(
            "Judge: trace %s already scored (%.2f), skipping",
            trace_id,
            trace.judge_score,
        )
        return {"trace_id": str(trace_id), "skipped": True}

    # Load domain/tone from inference via deployment chain
    row = (
        await db.execute(
            text(
                "SELECT i.domain, i.tone"
                " FROM deployments d"
                " JOIN generations g ON g.id = d.generation_id"
                " JOIN inferences i ON i.id = g.inference_id"
                " WHERE d.id = :dep"
            ),
            {"dep": str(deployment_id)},
        )
    ).mappings().first()

    domain = (row["domain"] if row else None) or "general"
    tone = (row["tone"] if row else None) or "professional"

    # Load up to 3 eval_pairs for context
    pair_rows = (
        await db.execute(
            text(
                "SELECT ep.query, ep.expected_answer"
                " FROM eval_pairs ep"
                " JOIN generations g ON g.id = ep.generation_id"
                " JOIN deployments d ON d.generation_id = g.id"
                " WHERE d.id = :dep"
                " ORDER BY ep.created_at ASC LIMIT 3"
            ),
            {"dep": str(deployment_id)},
        )
    ).mappings().all()
    eval_pairs = [dict(r) for r in pair_rows]

    prompt = _build_judge_prompt(domain=domain, tone=tone, eval_pairs=eval_pairs)

    client = anthropic.AsyncAnthropic()
    raw_response: str | None = None
    score: float | None = None
    reason: str | None = None

    for attempt in range(2):
        try:
            msg = await client.messages.create(
                model=_JUDGE_MODEL,
                max_tokens=128,
                messages=[{"role": "user", "content": prompt}],
            )
            raw_response = msg.content[0].text
            score, reason = _parse_judge_response(raw_response)
            if score is not None:
                break
            logger.warning(
                "Judge parse failed on attempt %d for trace %s",
                attempt + 1,
                trace_id,
            )
        except Exception as exc:
            logger.warning("Judge LLM call failed on attempt %d: %s", attempt + 1, exc)

    if score is None:
        global _judge_parse_failures
        _judge_parse_failures += 1
        logger.warning(
            "judge_parse_failures_total=%d — trace %s: all parse attempts failed",
            _judge_parse_failures,
            trace_id,
        )
        return {"trace_id": str(trace_id), "judge_score": None, "skipped": False}

    await update_judge_score(
        db,
        trace_id=trace_id,
        score=score,
        prompt_sent=prompt,
        raw_response=raw_response or "",
    )

    logger.info("Judge scored trace %s: %.2f (%s)", trace_id, score, reason)
    return {"trace_id": str(trace_id), "judge_score": score, "reason": reason}
