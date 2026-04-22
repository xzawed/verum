"""Pydantic models for the OBSERVE stage."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, Field


class TraceRecord(BaseModel):
    """Input data for a single LLM call trace. Created by client.record()."""

    deployment_id: uuid.UUID
    variant: str = Field(description="'baseline' or a variant name like 'cot'")
    model: str = Field(description="Exact model name, e.g. 'grok-2-1212'")
    input_tokens: int
    output_tokens: int
    latency_ms: int
    error: str | None = None
    cost_usd: float = 0.0


class SpanRecord(BaseModel):
    """One span row, attached to a trace."""

    trace_id: uuid.UUID
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    cost_usd: float
    error: str | None = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))


class DailyMetric(BaseModel):
    """Aggregated metrics for one calendar day."""

    date: str  # ISO date string "YYYY-MM-DD"
    total_cost_usd: float
    call_count: int
    p95_latency_ms: int
    avg_judge_score: float | None
