# Phase 4-A: OBSERVE Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every `verum.chat()` call in ArcanaInsight produces a persisted trace with latency, token count, cost, and LLM-as-Judge quality score; the dashboard shows 7-day trends.

**Architecture:** Explicit push model — ArcanaInsight calls `client.record()` after each LLM call; the backend saves trace+span, calculates cost from DB-managed pricing, and enqueues a `"judge"` job that calls Claude Sonnet 4.6 asynchronously. Dashboard adds an ObserveSection to the existing `/repos/[id]` page.

**Tech Stack:** Python asyncio worker (SQLAlchemy text() queries), Next.js App Router (Drizzle ORM raw sql), Recharts (already installed), httpx (SDK).

**Spec:** `docs/superpowers/specs/2026-04-23-phase4a-observe-design.md`

---

## File Map

**Create:**
- `apps/api/alembic/versions/0009_phase4a_observe.py` — 4 new tables + seed pricing data
- `apps/api/src/loop/observe/models.py` — TraceRecord, SpanRecord Pydantic models
- `apps/api/src/loop/observe/repository.py` — insert_trace(), update_judge_score(), get_daily_metrics()
- `apps/api/src/db/models/traces.py` — SQLAlchemy ORM model for traces table
- `apps/api/src/worker/handlers/judge.py` — handle_judge: LLM-as-Judge async handler
- `apps/api/tests/loop/observe/test_repository.py` — repository unit tests
- `apps/api/tests/worker/handlers/test_judge.py` — judge handler unit tests
- `apps/dashboard/src/app/api/v1/traces/route.ts` — GET (list) + POST (ingest)
- `apps/dashboard/src/app/api/v1/traces/[id]/route.ts` — GET (detail + span + judge)
- `apps/dashboard/src/app/api/v1/metrics/route.ts` — GET (7-day aggregation)
- `apps/dashboard/src/app/api/v1/feedback/route.ts` — POST (user_feedback update)
- `apps/dashboard/src/app/repos/[id]/ObserveSection.tsx` — metrics + chart + trace table
- `apps/dashboard/src/components/SpanWaterfall.tsx` — slide-over panel

**Modify:**
- `apps/api/src/worker/runner.py` — add `"judge": handle_judge` to `_HANDLERS`
- `packages/sdk-python/src/verum/client.py` — add `record()` method
- `apps/dashboard/src/lib/db/schema.ts` — add 4 new table definitions
- `apps/dashboard/src/lib/db/queries.ts` — add trace/metrics read queries
- `apps/dashboard/src/lib/db/jobs.ts` — add insertTrace(), updateFeedback()
- `apps/dashboard/src/app/repos/[id]/StagesView.tsx` — mount ObserveSection

---

## Task 1: Alembic Migration — 4 Tables + Seed Data

**Files:**
- Create: `apps/api/alembic/versions/0009_phase4a_observe.py`

- [ ] **Step 1: Write the migration file**

```python
# apps/api/alembic/versions/0009_phase4a_observe.py
"""Create model_pricing, traces, spans, judge_prompts tables.

Revision ID: 0009_phase4a_observe
Revises: 0008_metric_profile_deployments
Create Date: 2026-04-23
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0009_phase4a_observe"
down_revision: Union[str, None] = "0008_metric_profile_deployments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "model_pricing",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("model_name", sa.Text, nullable=False, unique=True),
        sa.Column("input_per_1m_usd", sa.Numeric(10, 6), nullable=False),
        sa.Column("output_per_1m_usd", sa.Numeric(10, 6), nullable=False),
        sa.Column("provider", sa.Text, nullable=False),
        sa.Column(
            "effective_from",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_model_pricing_model_name", "model_pricing", ["model_name"], unique=True)

    op.create_table(
        "traces",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "deployment_id",
            UUID(as_uuid=True),
            sa.ForeignKey("deployments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("variant", sa.Text, nullable=False, server_default="baseline"),
        sa.Column("user_feedback", sa.SmallInteger, nullable=True),
        sa.Column("judge_score", sa.Float, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_traces_deployment_id", "traces", ["deployment_id"])
    op.create_index("ix_traces_created_at", "traces", ["created_at"])

    op.create_table(
        "spans",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "trace_id",
            UUID(as_uuid=True),
            sa.ForeignKey("traces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("model", sa.Text, nullable=False),
        sa.Column("input_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=False, server_default="0"),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_spans_trace_id", "spans", ["trace_id"])

    op.create_table(
        "judge_prompts",
        sa.Column(
            "trace_id",
            UUID(as_uuid=True),
            sa.ForeignKey("traces.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("prompt_sent", sa.Text, nullable=False),
        sa.Column("raw_response", sa.Text, nullable=False),
        sa.Column(
            "judged_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # Seed initial pricing data
    op.execute("""
        INSERT INTO model_pricing (model_name, input_per_1m_usd, output_per_1m_usd, provider) VALUES
        ('grok-2-1212',       2.000000, 10.000000, 'xai'),
        ('grok-2-mini',       0.200000,  0.400000, 'xai'),
        ('claude-sonnet-4-6', 3.000000, 15.000000, 'anthropic'),
        ('claude-haiku-4-5',  0.800000,  4.000000, 'anthropic'),
        ('gpt-4o',            2.500000, 10.000000, 'openai'),
        ('gpt-4o-mini',       0.150000,  0.600000, 'openai')
    """)


def downgrade() -> None:
    op.drop_table("judge_prompts")
    op.drop_table("spans")
    op.drop_table("traces")
    op.drop_table("model_pricing")
```

- [ ] **Step 2: Apply migration locally**

```bash
cd apps/api
alembic upgrade head
```

Expected output ends with: `Running upgrade 0008_metric_profile_deployments -> 0009_phase4a_observe`

- [ ] **Step 3: Verify tables exist**

```bash
cd apps/api
python - <<'EOF'
import asyncio
from sqlalchemy import text
from src.db.session import AsyncSessionLocal

async def check():
    async with AsyncSessionLocal() as db:
        for table in ["model_pricing", "traces", "spans", "judge_prompts"]:
            r = await db.execute(text(f"SELECT COUNT(*) FROM {table}"))
            print(f"{table}: {r.scalar()} rows")

asyncio.run(check())
EOF
```

Expected: `model_pricing: 6 rows`, others: `0 rows`

- [ ] **Step 4: Commit**

```bash
git add apps/api/alembic/versions/0009_phase4a_observe.py
git commit -m "feat(observe): F-4.1 migration — model_pricing, traces, spans, judge_prompts tables"
```

---

## Task 2: Python Pydantic Models

**Files:**
- Create: `apps/api/src/loop/observe/models.py`
- Create: `apps/api/tests/loop/observe/__init__.py`
- Create: `apps/api/tests/loop/observe/test_repository.py` (stub for now)

- [ ] **Step 1: Write the failing test**

```python
# apps/api/tests/loop/observe/test_repository.py
"""Tests for observe repository. Requires a live DB (integration test)."""
from __future__ import annotations

import uuid
import pytest

from src.loop.observe.models import TraceRecord, SpanRecord


def test_trace_record_defaults():
    rec = TraceRecord(
        deployment_id=uuid.uuid4(),
        variant="cot",
        model="grok-2-1212",
        input_tokens=512,
        output_tokens=284,
        latency_ms=980,
    )
    assert rec.error is None
    assert rec.cost_usd == 0.0


def test_span_record_cost_calculation():
    rec = SpanRecord(
        trace_id=uuid.uuid4(),
        model="grok-2-1212",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        latency_ms=1000,
        cost_usd=12.0,  # 2.0 input + 10.0 output
    )
    assert rec.cost_usd == 12.0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd apps/api
pytest tests/loop/observe/test_repository.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.loop.observe.models'`

- [ ] **Step 3: Write the models**

```python
# apps/api/src/loop/observe/models.py
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
```

Also create the `__init__.py`:
```python
# apps/api/src/loop/observe/__init__.py
```
```python
# apps/api/tests/loop/observe/__init__.py
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd apps/api
pytest tests/loop/observe/test_repository.py -v
```

Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/loop/observe/models.py apps/api/src/loop/observe/__init__.py \
        apps/api/tests/loop/observe/__init__.py apps/api/tests/loop/observe/test_repository.py
git commit -m "feat(observe): TraceRecord, SpanRecord, DailyMetric Pydantic models"
```

---

## Task 3: SQLAlchemy Trace Model

**Files:**
- Create: `apps/api/src/db/models/traces.py`
- Modify: `apps/api/src/db/models/__init__.py`

- [ ] **Step 1: Write the failing test**

Add to `apps/api/tests/loop/observe/test_repository.py`:

```python
def test_trace_model_import():
    from src.db.models.traces import Trace
    assert Trace.__tablename__ == "traces"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd apps/api
pytest tests/loop/observe/test_repository.py::test_trace_model_import -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.db.models.traces'`

- [ ] **Step 3: Write the SQLAlchemy model**

Look up an existing model for the exact Base import. Run:
```bash
head -20 apps/api/src/db/models/generations.py
```
Copy the exact `Base` import line. Then write:

```python
# apps/api/src/db/models/traces.py
"""SQLAlchemy ORM model for the traces table."""
from __future__ import annotations

import uuid

from sqlalchemy import DateTime, Float, SmallInteger, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base  # adjust if your Base is elsewhere


class Trace(Base):
    __tablename__ = "traces"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    deployment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    variant: Mapped[str] = mapped_column(String(64), nullable=False, server_default="baseline")
    user_feedback: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    judge_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
```

- [ ] **Step 4: Register in `__init__.py`**

Open `apps/api/src/db/models/__init__.py`. Add:
```python
from src.db.models.traces import Trace  # noqa: F401
```
alongside the existing imports.

- [ ] **Step 5: Run test to verify it passes**

```bash
cd apps/api
pytest tests/loop/observe/test_repository.py -v
```

Expected: `3 passed`

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/db/models/traces.py apps/api/src/db/models/__init__.py
git commit -m "feat(observe): SQLAlchemy Trace ORM model"
```

---

## Task 4: Python Observe Repository

**Files:**
- Create: `apps/api/src/loop/observe/repository.py`

- [ ] **Step 1: Add integration tests** (require live DB; mark with `pytest.mark.integration`)

```python
# Add to apps/api/tests/loop/observe/test_repository.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.loop.observe.repository import calculate_cost


def test_calculate_cost_known_model():
    # 1M input + 1M output of grok-2-1212 = 2.00 + 10.00 = 12.00
    pricing = {"input_per_1m_usd": 2.0, "output_per_1m_usd": 10.0}
    cost = calculate_cost(
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        pricing=pricing,
    )
    assert abs(cost - 12.0) < 0.0001


def test_calculate_cost_zero_for_no_pricing():
    cost = calculate_cost(input_tokens=500, output_tokens=300, pricing=None)
    assert cost == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd apps/api
pytest tests/loop/observe/test_repository.py::test_calculate_cost_known_model -v
```

Expected: FAIL with `ImportError`

- [ ] **Step 3: Write the repository**

```python
# apps/api/src/loop/observe/repository.py
"""Database I/O for the OBSERVE stage."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.traces import Trace
from src.loop.observe.models import DailyMetric, TraceRecord

_logger = logging.getLogger(__name__)


def calculate_cost(
    input_tokens: int,
    output_tokens: int,
    pricing: dict[str, float] | None,
) -> float:
    """Calculate USD cost from token counts and pricing row. Returns 0.0 if pricing is None."""
    if pricing is None:
        return 0.0
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
        _logger.warning("model_pricing: no pricing found for model=%s, cost stored as 0", model)
        return None
    return dict(row)


async def insert_trace(
    db: AsyncSession,
    record: TraceRecord,
) -> uuid.UUID:
    """Insert trace + span atomically. Returns the new trace_id."""
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
    """Write judge score to traces and full prompt to judge_prompts."""
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
    """Set user_feedback (-1 or 1). Returns False if trace not found."""
    result = await db.execute(
        text(
            "UPDATE traces SET user_feedback = :score WHERE id = :id RETURNING id"
        ),
        {"score": score, "id": str(trace_id)},
    )
    await db.commit()
    return result.rowcount == 1


async def get_daily_metrics(
    db: AsyncSession,
    deployment_id: uuid.UUID,
    days: int = 7,
) -> list[DailyMetric]:
    """Return one DailyMetric per calendar day for the past N days."""
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
                "   AND t.created_at >= NOW() - INTERVAL ':days days'"
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd apps/api
pytest tests/loop/observe/test_repository.py -v
```

Expected: `5 passed` (3 from earlier + 2 new)

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/loop/observe/repository.py
git commit -m "feat(observe): observe repository — insert_trace, update_judge_score, get_daily_metrics"
```

---

## Task 5: Judge Worker Handler

**Files:**
- Create: `apps/api/src/worker/handlers/judge.py`
- Create: `apps/api/tests/worker/handlers/test_judge.py`

- [ ] **Step 1: Write the failing test**

```python
# apps/api/tests/worker/handlers/test_judge.py
"""Tests for the judge handler."""
from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.worker.handlers.judge import _build_judge_prompt, _parse_judge_response


def test_build_judge_prompt_contains_domain():
    prompt = _build_judge_prompt(
        domain="divination/tarot",
        tone="mystical",
        eval_pairs=[
            {"query": "What does The Star mean?", "expected_answer": "Hope and renewal"},
        ],
    )
    assert "divination/tarot" in prompt
    assert "mystical" in prompt
    assert "The Star" in prompt


def test_parse_judge_response_valid():
    raw = json.dumps({"score": 0.82, "reason": "Good answer"})
    score, reason = _parse_judge_response(raw)
    assert abs(score - 0.82) < 0.001
    assert reason == "Good answer"


def test_parse_judge_response_clamped():
    raw = json.dumps({"score": 1.5, "reason": "Over limit"})
    score, _ = _parse_judge_response(raw)
    assert score == 1.0


def test_parse_judge_response_invalid_returns_none():
    score, reason = _parse_judge_response("not json at all")
    assert score is None
    assert reason is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd apps/api
pytest tests/worker/handlers/test_judge.py -v
```

Expected: FAIL with `ImportError`

- [ ] **Step 3: Write the handler**

```python
# apps/api/src/worker/handlers/judge.py
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
    trace_id = uuid.UUID(payload["trace_id"])
    deployment_id = uuid.UUID(payload["deployment_id"])

    # Idempotency: skip if already scored
    trace = (
        await db.execute(select(Trace).where(Trace.id == trace_id))
    ).scalar_one_or_none()
    if trace is None:
        raise ValueError(f"Trace {trace_id} not found")
    if trace.judge_score is not None:
        logger.info("Judge: trace %s already scored (%.2f), skipping", trace_id, trace.judge_score)
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

    client = anthropic.Anthropic()
    raw_response: str | None = None
    score: float | None = None
    reason: str | None = None

    for attempt in range(2):
        try:
            msg = client.messages.create(
                model=_JUDGE_MODEL,
                max_tokens=128,
                messages=[{"role": "user", "content": prompt}],
            )
            raw_response = msg.content[0].text
            score, reason = _parse_judge_response(raw_response)
            if score is not None:
                break
            logger.warning("Judge parse failed on attempt %d for trace %s", attempt + 1, trace_id)
        except Exception as exc:
            logger.warning("Judge LLM call failed on attempt %d: %s", attempt + 1, exc)

    if score is None:
        logger.warning("Judge gave up on trace %s — leaving judge_score NULL", trace_id)
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd apps/api
pytest tests/worker/handlers/test_judge.py -v
```

Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/worker/handlers/judge.py apps/api/tests/worker/handlers/test_judge.py
git commit -m "feat(observe): handle_judge — LLM-as-Judge async worker handler"
```

---

## Task 6: Register Judge Handler in Runner

**Files:**
- Modify: `apps/api/src/worker/runner.py`

- [ ] **Step 1: Add import and register in `_HANDLERS`**

In `apps/api/src/worker/runner.py`, find the existing imports block:
```python
from .handlers.analyze import handle_analyze
from .handlers.deploy import handle_deploy
from .handlers.generate import handle_generate
from .handlers.harvest import handle_harvest
from .handlers.infer import handle_infer
from .handlers.retrieve import handle_retrieve
```

Add after the last import:
```python
from .handlers.judge import handle_judge
```

Find the `_HANDLERS` dict:
```python
_HANDLERS = {
    "analyze": handle_analyze,
    "infer": handle_infer,
    "harvest": handle_harvest,
    "retrieve": handle_retrieve,
    "generate": handle_generate,
    "deploy": handle_deploy,
}
```

Add `"judge"` entry:
```python
_HANDLERS = {
    "analyze": handle_analyze,
    "infer": handle_infer,
    "harvest": handle_harvest,
    "retrieve": handle_retrieve,
    "generate": handle_generate,
    "deploy": handle_deploy,
    "judge": handle_judge,
}
```

- [ ] **Step 2: Verify import is clean**

```bash
cd apps/api
python -c "from src.worker.runner import _HANDLERS; print(list(_HANDLERS.keys()))"
```

Expected: `['analyze', 'infer', 'harvest', 'retrieve', 'generate', 'deploy', 'judge']`

- [ ] **Step 3: Run full test suite to catch regressions**

```bash
cd apps/api
pytest tests/ -v --tb=short -q
```

Expected: All previously passing tests still pass.

- [ ] **Step 4: Commit**

```bash
git add apps/api/src/worker/runner.py
git commit -m "feat(observe): register judge handler in worker runner"
```

---

## Task 7: Drizzle Schema — Add 4 New Tables

**Files:**
- Modify: `apps/dashboard/src/lib/db/schema.ts`

The Drizzle schema mirrors the Alembic SoT via `drizzle-kit pull`. Run it first:

- [ ] **Step 1: Run drizzle-kit pull**

```bash
cd apps/dashboard
pnpm db:pull
```

If `pnpm db:pull` is not defined in `package.json`, check the script name:
```bash
cat apps/dashboard/package.json | grep -A5 '"scripts"'
```
Then run the correct command. This regenerates `src/lib/db/schema.ts` with the new tables.

- [ ] **Step 2: Verify new tables appear in schema.ts**

```bash
grep -n "model_pricing\|traces\|spans\|judge_prompts" apps/dashboard/src/lib/db/schema.ts
```

Expected: 4 matches, one per new table.

- [ ] **Step 3: If drizzle-kit pull is unavailable, add manually**

Open `apps/dashboard/src/lib/db/schema.ts` and append the following at the end, matching the existing table definition style:

```typescript
export const model_pricing = pgTable("model_pricing", {
  id: uuid("id").primaryKey().defaultRandom(),
  model_name: text("model_name").notNull().unique(),
  input_per_1m_usd: numeric("input_per_1m_usd", { precision: 10, scale: 6 }).notNull(),
  output_per_1m_usd: numeric("output_per_1m_usd", { precision: 10, scale: 6 }).notNull(),
  provider: text("provider").notNull(),
  effective_from: timestamp("effective_from", { withTimezone: true }).notNull().defaultNow(),
});

export const traces = pgTable("traces", {
  id: uuid("id").primaryKey().defaultRandom(),
  deployment_id: uuid("deployment_id").notNull(),
  variant: text("variant").notNull().default("baseline"),
  user_feedback: smallint("user_feedback"),
  judge_score: doublePrecision("judge_score"),
  created_at: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
});

export const spans = pgTable("spans", {
  id: uuid("id").primaryKey().defaultRandom(),
  trace_id: uuid("trace_id").notNull(),
  model: text("model").notNull(),
  input_tokens: integer("input_tokens").notNull().default(0),
  output_tokens: integer("output_tokens").notNull().default(0),
  latency_ms: integer("latency_ms").notNull().default(0),
  cost_usd: numeric("cost_usd", { precision: 10, scale: 6 }).notNull().default("0"),
  error: text("error"),
  started_at: timestamp("started_at", { withTimezone: true }).notNull().defaultNow(),
});

export const judge_prompts = pgTable("judge_prompts", {
  trace_id: uuid("trace_id").primaryKey(),
  prompt_sent: text("prompt_sent").notNull(),
  raw_response: text("raw_response").notNull(),
  judged_at: timestamp("judged_at", { withTimezone: true }).notNull().defaultNow(),
});
```

Make sure `pgTable`, `uuid`, `text`, `timestamp`, `integer`, `numeric`, `smallint`, `doublePrecision` are all imported at the top of `schema.ts`. Add any missing imports from `drizzle-orm/pg-core`.

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd apps/dashboard
pnpm tsc --noEmit
```

Expected: No errors.

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/src/lib/db/schema.ts
git commit -m "feat(observe): add traces, spans, model_pricing, judge_prompts to Drizzle schema"
```

---

## Task 8: Drizzle DB Functions (queries.ts + jobs.ts)

**Files:**
- Modify: `apps/dashboard/src/lib/db/queries.ts`
- Modify: `apps/dashboard/src/lib/db/jobs.ts`

- [ ] **Step 1: Add read queries to `queries.ts`**

Open `apps/dashboard/src/lib/db/queries.ts`. Add at the end:

```typescript
// ── OBSERVE ───────────────────────────────────────────────────

export async function getTraceList(
  deploymentId: string,
  page: number = 1,
  limit: number = 20,
) {
  const offset = (page - 1) * limit;
  const rows = await db.execute(
    sql`
      SELECT
        t.id, t.variant, t.user_feedback, t.judge_score, t.created_at,
        s.latency_ms, s.cost_usd, s.model, s.input_tokens, s.output_tokens, s.error
      FROM traces t
      JOIN spans s ON s.trace_id = t.id
      WHERE t.deployment_id = ${deploymentId}::uuid
      ORDER BY t.created_at DESC
      LIMIT ${limit} OFFSET ${offset}
    `,
  );

  const countRow = await db.execute(
    sql`SELECT COUNT(*)::int AS total FROM traces WHERE deployment_id = ${deploymentId}::uuid`,
  );

  return {
    traces: rows.rows,
    total: Number((countRow.rows[0] as Record<string, unknown>)?.total ?? 0),
    page,
  };
}

export async function getTraceDetail(traceId: string) {
  const traceRows = await db.execute(
    sql`
      SELECT
        t.id, t.variant, t.user_feedback, t.judge_score, t.created_at,
        s.latency_ms, s.cost_usd, s.model, s.input_tokens, s.output_tokens, s.error,
        jp.raw_response AS judge_raw_response, jp.judged_at
      FROM traces t
      JOIN spans s ON s.trace_id = t.id
      LEFT JOIN judge_prompts jp ON jp.trace_id = t.id
      WHERE t.id = ${traceId}::uuid
    `,
  );
  return traceRows.rows[0] ?? null;
}

export async function getDailyMetrics(deploymentId: string, days: number = 7) {
  const rows = await db.execute(
    sql`
      SELECT
        DATE(t.created_at AT TIME ZONE 'UTC')::text AS date,
        COALESCE(SUM(s.cost_usd), 0)::float AS total_cost_usd,
        COUNT(t.id)::int AS call_count,
        COALESCE(
          PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY s.latency_ms), 0
        )::int AS p95_latency_ms,
        AVG(t.judge_score)::float AS avg_judge_score
      FROM traces t
      JOIN spans s ON s.trace_id = t.id
      WHERE t.deployment_id = ${deploymentId}::uuid
        AND t.created_at >= NOW() - (${days} || ' days')::interval
      GROUP BY DATE(t.created_at AT TIME ZONE 'UTC')
      ORDER BY date ASC
    `,
  );
  return rows.rows;
}
```

Make sure `sql` is imported: `import { sql } from "drizzle-orm";`

- [ ] **Step 2: Add write functions to `jobs.ts`**

Open `apps/dashboard/src/lib/db/jobs.ts`. Add at the end:

```typescript
// ── OBSERVE ───────────────────────────────────────────────────

export async function insertTrace(opts: {
  deploymentId: string;
  variant: string;
  model: string;
  inputTokens: number;
  outputTokens: number;
  latencyMs: number;
  error: string | null;
  costUsd: string;
}): Promise<string> {
  const traceRows = await db.execute(
    sql`
      INSERT INTO traces (deployment_id, variant, created_at)
      VALUES (${opts.deploymentId}::uuid, ${opts.variant}, NOW())
      RETURNING id
    `,
  );
  const traceId = (traceRows.rows[0] as Record<string, unknown>).id as string;

  await db.execute(
    sql`
      INSERT INTO spans (trace_id, model, input_tokens, output_tokens, latency_ms, cost_usd, error, started_at)
      VALUES (${traceId}::uuid, ${opts.model}, ${opts.inputTokens}, ${opts.outputTokens},
              ${opts.latencyMs}, ${opts.costUsd}::numeric, ${opts.error}, NOW())
    `,
  );

  // Enqueue judge job
  await db.insert(verum_jobs).values({
    kind: "judge",
    payload: { trace_id: traceId, deployment_id: opts.deploymentId, variant: opts.variant },
    owner_user_id: await _getDeploymentOwner(opts.deploymentId),
  });

  return traceId;
}

async function _getDeploymentOwner(deploymentId: string): Promise<string> {
  const rows = await db.execute(
    sql`
      SELECT r.owner_user_id
      FROM deployments d
      JOIN generations g ON g.id = d.generation_id
      JOIN inferences i ON i.id = g.inference_id
      JOIN analyses a ON a.id = i.analysis_id
      JOIN repos r ON r.id = a.repo_id
      WHERE d.id = ${deploymentId}::uuid
    `,
  );
  return ((rows.rows[0] as Record<string, unknown>)?.owner_user_id as string) ?? "";
}

export async function updateFeedback(
  deploymentId: string,
  traceId: string,
  score: number,
): Promise<boolean> {
  // Verify trace belongs to this deployment before updating
  const result = await db.execute(
    sql`
      UPDATE traces SET user_feedback = ${score}
      WHERE id = ${traceId}::uuid AND deployment_id = ${deploymentId}::uuid
      RETURNING id
    `,
  );
  return (result.rowCount ?? 0) > 0;
}

export async function getModelPricing(
  modelName: string,
): Promise<{ input_per_1m_usd: string; output_per_1m_usd: string } | null> {
  const rows = await db.execute(
    sql`
      SELECT input_per_1m_usd::text, output_per_1m_usd::text
      FROM model_pricing WHERE model_name = ${modelName}
      ORDER BY effective_from DESC LIMIT 1
    `,
  );
  return (rows.rows[0] as Record<string, unknown> | undefined) as
    | { input_per_1m_usd: string; output_per_1m_usd: string }
    | null;
}
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd apps/dashboard
pnpm tsc --noEmit
```

Expected: No errors.

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/src/lib/db/queries.ts apps/dashboard/src/lib/db/jobs.ts
git commit -m "feat(observe): Drizzle DB functions — insertTrace, updateFeedback, getTraceList, getDailyMetrics"
```

---

## Task 9: Next.js API Routes

**Files:**
- Create: `apps/dashboard/src/app/api/v1/traces/route.ts`
- Create: `apps/dashboard/src/app/api/v1/traces/[id]/route.ts`
- Create: `apps/dashboard/src/app/api/v1/metrics/route.ts`
- Create: `apps/dashboard/src/app/api/v1/feedback/route.ts`

### 9-A: `POST /api/v1/traces` + `GET /api/v1/traces`

- [ ] **Step 1: Write `apps/dashboard/src/app/api/v1/traces/route.ts`**

```typescript
import { auth } from "@/auth";
import { getModelPricing, insertTrace } from "@/lib/db/jobs";
import { getTraceList } from "@/lib/db/queries";

// POST — SDK-facing: API key auth via X-Verum-API-Key header
export async function POST(req: Request) {
  const apiKey = req.headers.get("x-verum-api-key") ?? "";
  if (!apiKey) return new Response("unauthorized", { status: 401 });

  const body = await req.json() as {
    deployment_id: string;
    variant: string;
    model: string;
    input_tokens: number;
    output_tokens: number;
    latency_ms: number;
    error?: string | null;
  };

  // Validate deployment_id is a valid UUID format (basic check)
  if (!body.deployment_id || !body.model) {
    return new Response("bad request", { status: 400 });
  }

  // Verify api_key matches a deployment (deployment ID is the API key)
  if (apiKey !== body.deployment_id) {
    return new Response("unauthorized", { status: 401 });
  }

  // Calculate cost
  const pricing = await getModelPricing(body.model);
  let costUsd = "0";
  if (pricing) {
    const inputCost = (body.input_tokens / 1_000_000) * Number(pricing.input_per_1m_usd);
    const outputCost = (body.output_tokens / 1_000_000) * Number(pricing.output_per_1m_usd);
    costUsd = (inputCost + outputCost).toFixed(6);
  }

  try {
    const traceId = await insertTrace({
      deploymentId: body.deployment_id,
      variant: body.variant ?? "baseline",
      model: body.model,
      inputTokens: body.input_tokens,
      outputTokens: body.output_tokens,
      latencyMs: body.latency_ms,
      error: body.error ?? null,
      costUsd,
    });
    return Response.json({ trace_id: traceId }, { status: 201 });
  } catch {
    return new Response("deployment not found", { status: 404 });
  }
}

// GET — browser-facing: Auth.js session
export async function GET(req: Request) {
  const session = await auth();
  if (!session?.user) return new Response("unauthorized", { status: 401 });

  const { searchParams } = new URL(req.url);
  const deploymentId = searchParams.get("deployment_id") ?? "";
  const page = Number(searchParams.get("page") ?? "1");
  const limit = Number(searchParams.get("limit") ?? "20");

  if (!deploymentId) return new Response("deployment_id required", { status: 400 });

  const result = await getTraceList(deploymentId, page, limit);
  return Response.json(result, { headers: { "Cache-Control": "no-store" } });
}
```

### 9-B: `GET /api/v1/traces/[id]`

- [ ] **Step 2: Write `apps/dashboard/src/app/api/v1/traces/[id]/route.ts`**

```typescript
import { auth } from "@/auth";
import { getTraceDetail } from "@/lib/db/queries";

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const session = await auth();
  if (!session?.user) return new Response("unauthorized", { status: 401 });

  const { id } = await params;
  const trace = await getTraceDetail(id);
  if (!trace) return new Response("not found", { status: 404 });

  return Response.json(trace, { headers: { "Cache-Control": "no-store" } });
}
```

### 9-C: `GET /api/v1/metrics`

- [ ] **Step 3: Write `apps/dashboard/src/app/api/v1/metrics/route.ts`**

```typescript
import { auth } from "@/auth";
import { getDailyMetrics } from "@/lib/db/queries";

export async function GET(req: Request) {
  const session = await auth();
  if (!session?.user) return new Response("unauthorized", { status: 401 });

  const { searchParams } = new URL(req.url);
  const deploymentId = searchParams.get("deployment_id") ?? "";
  const days = Number(searchParams.get("days") ?? "7");

  if (!deploymentId) return new Response("deployment_id required", { status: 400 });

  const daily = await getDailyMetrics(deploymentId, days);
  return Response.json({ daily }, { headers: { "Cache-Control": "no-store" } });
}
```

### 9-D: `POST /api/v1/feedback`

- [ ] **Step 4: Write `apps/dashboard/src/app/api/v1/feedback/route.ts`**

```typescript
import { updateFeedback } from "@/lib/db/jobs";

export async function POST(req: Request) {
  const apiKey = req.headers.get("x-verum-api-key") ?? "";
  if (!apiKey) return new Response("unauthorized", { status: 401 });

  const body = await req.json() as { trace_id: string; score: number };

  if (!body.trace_id || (body.score !== 1 && body.score !== -1)) {
    return new Response("score must be 1 or -1", { status: 400 });
  }

  // API key is the deployment_id; use it to scope the feedback update
  const ok = await updateFeedback(apiKey, body.trace_id, body.score);
  if (!ok) return new Response("not found", { status: 404 });

  return new Response(null, { status: 204 });
}
```

- [ ] **Step 5: Verify TypeScript compiles**

```bash
cd apps/dashboard
pnpm tsc --noEmit
```

Expected: No errors.

- [ ] **Step 6: Commit**

```bash
git add apps/dashboard/src/app/api/v1/traces/ \
        apps/dashboard/src/app/api/v1/metrics/ \
        apps/dashboard/src/app/api/v1/feedback/
git commit -m "feat(observe): F-4.1 API routes — POST /traces, GET /traces, GET /metrics, POST /feedback"
```

---

## Task 10: Python SDK — `client.record()`

**Files:**
- Modify: `packages/sdk-python/src/verum/client.py`

- [ ] **Step 1: Write the failing test**

Check existing test file location:
```bash
ls packages/sdk-python/tests/
```

Add to the existing test file (or create `packages/sdk-python/tests/test_client.py`):

```python
# In packages/sdk-python/tests/test_client.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from verum import Client


@pytest.mark.asyncio
async def test_record_returns_trace_id():
    client = Client(api_url="http://localhost:8080", api_key="test-key")
    mock_response = MagicMock()
    mock_response.json.return_value = {"trace_id": "abc-123"}
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_http:
        mock_http.return_value.__aenter__ = AsyncMock(return_value=mock_http.return_value)
        mock_http.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_http.return_value.post = AsyncMock(return_value=mock_response)

        trace_id = await client.record(
            deployment_id="dep-uuid",
            variant="cot",
            model="grok-2-1212",
            input_tokens=512,
            output_tokens=284,
            latency_ms=980,
        )

    assert trace_id == "abc-123"
    mock_http.return_value.post.assert_called_once()
    call_kwargs = mock_http.return_value.post.call_args
    assert "/api/v1/traces" in call_kwargs[0][0]
    body = call_kwargs[1]["json"]
    assert body["deployment_id"] == "dep-uuid"
    assert body["model"] == "grok-2-1212"
    assert body["input_tokens"] == 512
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd packages/sdk-python
pytest tests/ -v -k "test_record_returns_trace_id"
```

Expected: FAIL with `AttributeError: 'Client' object has no attribute 'record'`

- [ ] **Step 3: Add `record()` to `client.py`**

In `packages/sdk-python/src/verum/client.py`, after the `feedback()` method and before `_get_deployment_config()`, add:

```python
    async def record(
        self,
        *,
        deployment_id: str,
        variant: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: int,
        error: str | None = None,
    ) -> str:
        """Record an LLM call to Verum. Returns trace_id.

        Call immediately after the LLM SDK returns. Pass the returned
        trace_id to feedback() if the user provides a rating.

        Args:
            deployment_id: From client.chat() response["deployment_id"].
            variant: From client.chat() response["routed_to"].
            model: Exact model string used (e.g. "grok-2-1212").
            input_tokens: From LLM response usage.prompt_tokens.
            output_tokens: From LLM response usage.completion_tokens.
            latency_ms: Wall-clock time from request start to response end.
            error: Error message if the LLM call failed; None on success.

        Returns:
            trace_id string to pass to feedback().
        """
        async with httpx.AsyncClient() as http:
            resp = await http.post(
                f"{self._api_url}/api/v1/traces",
                json={
                    "deployment_id": deployment_id,
                    "variant": variant,
                    "model": model,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "latency_ms": latency_ms,
                    "error": error,
                },
                headers=self._headers(),
                timeout=5.0,
            )
            resp.raise_for_status()
            return resp.json()["trace_id"]
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd packages/sdk-python
pytest tests/ -v -k "test_record_returns_trace_id"
```

Expected: `1 passed`

- [ ] **Step 5: Commit**

```bash
git add packages/sdk-python/src/verum/client.py packages/sdk-python/tests/
git commit -m "feat(observe): F-4.1 SDK client.record() — send trace to Verum after LLM call"
```

---

## Task 11: Dashboard — ObserveSection Component

**Files:**
- Create: `apps/dashboard/src/app/repos/[id]/ObserveSection.tsx`

- [ ] **Step 1: Check Recharts import pattern**

```bash
grep -r "from 'recharts'" apps/dashboard/src --include="*.tsx" | head -5
```

Note the exact import style used in existing chart components.

- [ ] **Step 2: Write `ObserveSection.tsx`**

```tsx
// apps/dashboard/src/app/repos/[id]/ObserveSection.tsx
"use client";

import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import SpanWaterfall from "@/components/SpanWaterfall";

interface DailyMetric {
  date: string;
  total_cost_usd: number;
  call_count: number;
  p95_latency_ms: number;
  avg_judge_score: number | null;
}

interface TraceRow {
  id: string;
  variant: string;
  latency_ms: number;
  cost_usd: string;
  judge_score: number | null;
  user_feedback: number | null;
  created_at: string;
}

interface Props {
  deploymentId: string;
}

export default function ObserveSection({ deploymentId }: Props) {
  const [daily, setDaily] = useState<DailyMetric[]>([]);
  const [traces, setTraces] = useState<TraceRow[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [days, setDays] = useState(7);
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      fetch(`/api/v1/metrics?deployment_id=${deploymentId}&days=${days}`).then((r) => r.json()),
      fetch(`/api/v1/traces?deployment_id=${deploymentId}&page=${page}`).then((r) => r.json()),
    ]).then(([metricsData, tracesData]) => {
      setDaily(metricsData.daily ?? []);
      setTraces(tracesData.traces ?? []);
      setTotal(tracesData.total ?? 0);
      setLoading(false);
    });
  }, [deploymentId, days, page]);

  // Derived summary metrics
  const totalCost = daily.reduce((s, d) => s + (d.total_cost_usd ?? 0), 0);
  const totalCalls = daily.reduce((s, d) => s + (d.call_count ?? 0), 0);
  const p95 = daily.length ? Math.max(...daily.map((d) => d.p95_latency_ms ?? 0)) : 0;
  const avgJudge =
    daily.filter((d) => d.avg_judge_score != null).length > 0
      ? daily.reduce((s, d) => s + (d.avg_judge_score ?? 0), 0) /
        daily.filter((d) => d.avg_judge_score != null).length
      : null;

  return (
    <div className="mt-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-white">[6] OBSERVE</h3>
        <select
          value={days}
          onChange={(e) => { setDays(Number(e.target.value)); setPage(1); }}
          className="bg-gray-800 border border-gray-700 text-gray-300 text-xs rounded px-2 py-1"
        >
          <option value={7}>최근 7일</option>
          <option value={30}>최근 30일</option>
        </select>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-4 gap-3 mb-4">
        <MetricCard label="총 비용" value={`$${totalCost.toFixed(4)}`} color="green" />
        <MetricCard label="P95 지연" value={`${p95.toLocaleString()}ms`} color="indigo" />
        <MetricCard label="호출 수" value={totalCalls.toLocaleString()} color="yellow" />
        <MetricCard
          label="평균 Judge"
          value={avgJudge != null ? avgJudge.toFixed(2) : "—"}
          color="red"
        />
      </div>

      {/* Daily Bar Chart */}
      {daily.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 mb-4">
          <p className="text-xs text-gray-500 mb-2">일별 비용 (USD)</p>
          <ResponsiveContainer width="100%" height={80}>
            <BarChart data={daily} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis
                dataKey="date"
                tick={{ fill: "#6b7280", fontSize: 10 }}
                tickFormatter={(v: string) => v.slice(5)}
              />
              <YAxis tick={{ fill: "#6b7280", fontSize: 10 }} />
              <Tooltip
                contentStyle={{ background: "#111827", border: "1px solid #374151", fontSize: 12 }}
                formatter={(value: number, name: string) => [
                  name === "total_cost_usd" ? `$${Number(value).toFixed(4)}` : value,
                  name === "total_cost_usd" ? "비용" : "호출",
                ]}
              />
              <Bar dataKey="total_cost_usd" fill="#4ade80" radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Trace Table */}
      <div className="border border-gray-800 rounded-lg overflow-hidden">
        <div className="grid grid-cols-6 gap-2 bg-gray-900 px-3 py-2 text-xs text-gray-500 border-b border-gray-800">
          <span className="col-span-2">Trace ID</span>
          <span>Variant</span>
          <span>지연</span>
          <span>비용</span>
          <span>Judge / 피드백</span>
        </div>
        {loading ? (
          <div className="px-3 py-4 text-center text-xs text-gray-500">불러오는 중...</div>
        ) : traces.length === 0 ? (
          <div className="px-3 py-4 text-center text-xs text-gray-500">
            아직 trace가 없습니다. ArcanaInsight에서 client.record()를 호출하면 여기 표시됩니다.
          </div>
        ) : (
          traces.map((t) => (
            <div
              key={t.id}
              onClick={() => setSelectedTraceId(t.id)}
              className="grid grid-cols-6 gap-2 px-3 py-2 text-xs text-gray-300 border-b border-gray-900 cursor-pointer hover:bg-gray-800 transition-colors"
            >
              <span className="col-span-2 font-mono text-blue-400 truncate">{t.id}</span>
              <span className={t.variant === "baseline" ? "text-gray-400" : "text-green-400"}>
                {t.variant}
              </span>
              <span>{t.latency_ms?.toLocaleString()}ms</span>
              <span>${Number(t.cost_usd).toFixed(4)}</span>
              <span>
                {t.judge_score != null ? (
                  <span className={t.judge_score >= 0.7 ? "text-green-400" : "text-yellow-400"}>
                    {t.judge_score.toFixed(2)}
                  </span>
                ) : (
                  <span className="text-gray-500 italic">채점 중...</span>
                )}{" "}
                {t.user_feedback === 1 ? "👍" : t.user_feedback === -1 ? "👎" : ""}
              </span>
            </div>
          ))
        )}
      </div>

      {/* Pagination */}
      {total > 20 && (
        <div className="flex justify-between items-center mt-3 text-xs text-gray-500">
          <span>총 {total.toLocaleString()}개</span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-2 py-1 bg-gray-800 rounded disabled:opacity-40"
            >
              이전
            </button>
            <span className="px-2 py-1">{page}</span>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={page * 20 >= total}
              className="px-2 py-1 bg-gray-800 rounded disabled:opacity-40"
            >
              다음
            </button>
          </div>
        </div>
      )}

      {/* Span Waterfall Slide-over */}
      {selectedTraceId && (
        <SpanWaterfall
          traceId={selectedTraceId}
          onClose={() => setSelectedTraceId(null)}
        />
      )}
    </div>
  );
}

function MetricCard({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color: "green" | "indigo" | "yellow" | "red";
}) {
  const colors = {
    green: "border-green-800 text-green-400",
    indigo: "border-indigo-800 text-indigo-400",
    yellow: "border-yellow-800 text-yellow-400",
    red: "border-red-800 text-red-400",
  };
  return (
    <div className={`bg-gray-950 border rounded-lg p-3 ${colors[color]}`}>
      <div className="text-lg font-bold">{value}</div>
      <div className="text-xs text-gray-500 mt-1">{label}</div>
    </div>
  );
}
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd apps/dashboard
pnpm tsc --noEmit
```

Expected: No errors.

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/src/app/repos/\[id\]/ObserveSection.tsx
git commit -m "feat(observe): F-4.3 ObserveSection — metric cards, 7-day chart, paginated trace table"
```

---

## Task 12: Dashboard — SpanWaterfall Slide-over

**Files:**
- Create: `apps/dashboard/src/components/SpanWaterfall.tsx`

- [ ] **Step 1: Write `SpanWaterfall.tsx`**

```tsx
// apps/dashboard/src/components/SpanWaterfall.tsx
"use client";

import { useEffect, useState } from "react";

interface TraceDetail {
  id: string;
  variant: string;
  user_feedback: number | null;
  judge_score: number | null;
  created_at: string;
  latency_ms: number;
  cost_usd: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  error: string | null;
  judge_raw_response: string | null;
  judged_at: string | null;
}

interface Props {
  traceId: string;
  onClose: () => void;
}

export default function SpanWaterfall({ traceId, onClose }: Props) {
  const [detail, setDetail] = useState<TraceDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetch(`/api/v1/traces/${traceId}`)
      .then((r) => r.json())
      .then((data) => {
        setDetail(data);
        setLoading(false);
      });
  }, [traceId]);

  // Parse judge reason from raw_response JSON
  let judgeReason: string | null = null;
  if (detail?.judge_raw_response) {
    try {
      judgeReason = JSON.parse(detail.judge_raw_response).reason ?? null;
    } catch {
      judgeReason = null;
    }
  }

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 z-40"
        onClick={onClose}
      />

      {/* Panel */}
      <div className="fixed right-0 top-0 h-full w-96 bg-gray-950 border-l border-gray-800 z-50 overflow-y-auto">
        <div className="flex items-center justify-between p-4 border-b border-gray-800">
          <h3 className="text-sm font-semibold text-white">Trace 상세</h3>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-white text-lg leading-none"
          >
            ×
          </button>
        </div>

        {loading ? (
          <div className="p-4 text-xs text-gray-500">불러오는 중...</div>
        ) : detail == null ? (
          <div className="p-4 text-xs text-red-400">Trace를 찾을 수 없습니다.</div>
        ) : (
          <div className="p-4 space-y-4">
            {/* Metadata */}
            <Section title="기본 정보">
              <Row label="ID" value={<span className="font-mono text-blue-400 text-xs">{detail.id}</span>} />
              <Row label="Variant" value={<span className="text-green-400">{detail.variant}</span>} />
              <Row
                label="피드백"
                value={
                  detail.user_feedback === 1
                    ? "👍 긍정"
                    : detail.user_feedback === -1
                    ? "👎 부정"
                    : "없음"
                }
              />
              <Row label="시각" value={new Date(detail.created_at).toLocaleString("ko-KR")} />
            </Section>

            {/* Latency bar */}
            <Section title="지연 시간">
              <div className="bg-gray-900 rounded p-3">
                <div className="flex justify-between text-xs text-gray-400 mb-1">
                  <span>{detail.model}</span>
                  <span className="font-mono">{detail.latency_ms?.toLocaleString()}ms</span>
                </div>
                <div className="h-4 bg-gray-800 rounded overflow-hidden">
                  <div
                    className="h-full bg-indigo-500 rounded"
                    style={{ width: `${Math.min(100, (detail.latency_ms / 3000) * 100)}%` }}
                  />
                </div>
              </div>
              {detail.error && (
                <p className="text-xs text-red-400 mt-2">오류: {detail.error}</p>
              )}
            </Section>

            {/* Cost breakdown */}
            <Section title="비용 분석">
              <Row label="입력 토큰" value={detail.input_tokens?.toLocaleString()} />
              <Row label="출력 토큰" value={detail.output_tokens?.toLocaleString()} />
              <Row
                label="총 비용"
                value={
                  <span className="text-green-400 font-mono">
                    ${Number(detail.cost_usd).toFixed(6)}
                  </span>
                }
              />
            </Section>

            {/* Judge score */}
            <Section title="Judge 평가">
              {detail.judge_score != null ? (
                <>
                  <div className="flex items-center gap-2 mb-2">
                    <div className="flex-1 h-2 bg-gray-800 rounded overflow-hidden">
                      <div
                        className={`h-full rounded ${
                          detail.judge_score >= 0.7 ? "bg-green-500" : "bg-yellow-500"
                        }`}
                        style={{ width: `${detail.judge_score * 100}%` }}
                      />
                    </div>
                    <span className="text-sm font-bold text-white w-10 text-right">
                      {detail.judge_score.toFixed(2)}
                    </span>
                  </div>
                  {judgeReason && (
                    <p className="text-xs text-gray-400 bg-gray-900 rounded p-2">{judgeReason}</p>
                  )}
                  {detail.judged_at && (
                    <p className="text-xs text-gray-600 mt-1">
                      채점: {new Date(detail.judged_at).toLocaleString("ko-KR")}
                    </p>
                  )}
                </>
              ) : (
                <p className="text-xs text-gray-500 italic">채점 중... (최대 60초 소요)</p>
              )}
            </Section>
          </div>
        )}
      </div>
    </>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">{title}</p>
      <div className="space-y-1">{children}</div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between text-xs">
      <span className="text-gray-500">{label}</span>
      <span className="text-gray-300">{value}</span>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd apps/dashboard
pnpm tsc --noEmit
```

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add apps/dashboard/src/components/SpanWaterfall.tsx
git commit -m "feat(observe): F-4.3 SpanWaterfall slide-over — latency bar, cost breakdown, judge score"
```

---

## Task 13: Wire ObserveSection into Repo Detail Page

**Files:**
- Modify: `apps/dashboard/src/app/repos/[id]/StagesView.tsx` (or `page.tsx` — check which file renders the DEPLOY section)

- [ ] **Step 1: Find where DEPLOY section is rendered**

```bash
grep -rn "DeploySection\|DEPLOY\|\[5\]" apps/dashboard/src/app/repos/[id]/ --include="*.tsx" | head -10
```

Note the exact component name and file.

- [ ] **Step 2: Add ObserveSection import**

In the file identified in Step 1, add the import:
```typescript
import ObserveSection from "./ObserveSection";
```

- [ ] **Step 3: Mount ObserveSection after DeploySection**

Find the block that renders the DEPLOY section. After it, add:

```tsx
{/* Only show OBSERVE when a deployment exists */}
{repoStatus?.latestDeployment?.id && (
  <ObserveSection deploymentId={repoStatus.latestDeployment.id} />
)}
```

The exact prop name (`repoStatus?.latestDeployment?.id`) depends on how the existing `StagesView` receives the deployment. Check the existing DeploySection props to find the correct field name.

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd apps/dashboard
pnpm tsc --noEmit
```

Expected: No errors.

- [ ] **Step 5: Start dev server and verify UI renders**

```bash
cd apps/dashboard
pnpm dev
```

Open `http://localhost:3000` → connect a repo → navigate to a repo with a completed DEPLOY. Verify:
- OBSERVE section appears below DEPLOY section
- Metric cards show (all zeros initially)
- Trace table shows "아직 trace가 없습니다." empty state
- Chart renders (empty or with bars once traces exist)

- [ ] **Step 6: Commit**

```bash
git add apps/dashboard/src/app/repos/\[id\]/
git commit -m "feat(observe): F-4.3 wire ObserveSection into repo detail page"
```

---

## Task 14: Push and Final Verification

- [ ] **Step 1: Run full Python test suite**

```bash
cd apps/api
pytest tests/ -v --tb=short -q
```

Expected: All tests pass.

- [ ] **Step 2: Run full TypeScript type check**

```bash
cd apps/dashboard
pnpm tsc --noEmit
```

Expected: No errors.

- [ ] **Step 3: Update ROADMAP.md**

Open `docs/ROADMAP.md`. In the Phase 4 table, change:

```markdown
| F-4.1 | OpenTelemetry-compatible trace/span ingestion (`POST /v1/traces`) | 🔲 |
| F-4.2 | Cost calculation: token count × pricing table (OpenAI, Anthropic, xAI) | 🔲 |
| F-4.3 | Dashboard: trace list + span waterfall view + cost/latency metrics | 🔲 |
| F-4.4 | User feedback collection: `verum.feedback(trace_id, score)` | 🔲 |
```

to:

```markdown
| F-4.1 | OpenTelemetry-compatible trace/span ingestion (`POST /v1/traces`) | ✅ |
| F-4.2 | Cost calculation: token count × pricing table (OpenAI, Anthropic, xAI) | ✅ |
| F-4.3 | Dashboard: trace list + span waterfall view + cost/latency metrics | ✅ |
| F-4.4 | User feedback collection: `verum.feedback(trace_id, score)` | ✅ |
```

- [ ] **Step 4: Final commit and push**

```bash
git add docs/ROADMAP.md
git commit -m "docs: mark F-4.1 F-4.2 F-4.3 F-4.4 complete in ROADMAP"
git push origin main
```

---

## ArcanaInsight Dogfood Validation

After all tasks complete, validate with ArcanaInsight:

1. Add `client.record()` call to the tarot reading endpoint (following the pattern in spec §3)
2. Make one tarot reading request
3. Verify in PostgreSQL:
   ```sql
   SELECT id, variant, judge_score, created_at FROM traces ORDER BY created_at DESC LIMIT 5;
   ```
4. Wait 60 seconds, re-run query — `judge_score` should be populated
5. Open Verum dashboard → repo detail → OBSERVE section → confirm trace appears with judge score
6. Click the trace row → SpanWaterfall opens with cost breakdown and judge reasoning
