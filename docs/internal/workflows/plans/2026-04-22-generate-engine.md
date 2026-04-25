# Phase 3 GENERATE Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the [4] GENERATE stage — after HARVEST completes, Claude Sonnet 4.6 automatically generates 5 prompt variants, a recommended RAG config, and 20 eval Q/A pairs, all persisted in PostgreSQL and visible on the dashboard.

**Architecture:** HARVEST worker handler chains to a new `generate` job. The GENERATE engine makes 3 sequential Claude API calls (prompt variants → RAG config → eval pairs). Results go into 4 new tables (`generations`, `prompt_variants`, `rag_configs`, `eval_pairs`). Dashboard StagesView gains a [4] GENERATE section. Semantic chunking is added to `chunker.py` as an alternative splitter.

**Tech Stack:** Python 3.13, asyncio, SQLAlchemy 2, Alembic, `anthropic` SDK, Next.js 16, Drizzle ORM.

---

## File Map

| Action | Path | Purpose |
|---|---|---|
| Create | `apps/api/alembic/versions/0006_phase3_generate.py` | 4 new tables |
| Create | `apps/api/src/db/models/generations.py` | SQLAlchemy ORM model |
| Create | `apps/api/src/loop/generate/models.py` | Pydantic output models |
| Create | `apps/api/src/loop/generate/engine.py` | 3 Claude API calls |
| Create | `apps/api/src/loop/generate/repository.py` | DB I/O |
| Create | `apps/api/src/worker/handlers/generate.py` | Worker handler |
| Modify | `apps/api/src/worker/handlers/harvest.py` | Chain → GENERATE |
| Modify | `apps/api/src/worker/runner.py` | Register handler |
| Modify | `apps/api/src/loop/harvest/chunker.py` | Add semantic_split() |
| Modify | `apps/api/src/loop/harvest/pipeline.py` | Wire semantic strategy |
| Modify | `apps/dashboard/src/lib/db/queries.ts` | Add generation to RepoStatus |
| Modify | `apps/dashboard/src/app/repos/[id]/StagesView.tsx` | [4] GENERATE section |
| Modify | `apps/dashboard/src/app/repos/[id]/actions.ts` | rerunGenerate action |
| Modify | `README.md` | Fix Voyage AI (not OpenAI) in tech stack |
| Create | `apps/api/tests/loop/generate/test_engine.py` | Smoke tests |

---

## Task 1: Alembic Migration — 4 GENERATE Tables

**Files:**
- Create: `apps/api/alembic/versions/0006_phase3_generate.py`

- [ ] **Step 1: Write the migration file**

```python
"""Phase 3 GENERATE tables: generations, prompt_variants, rag_configs, eval_pairs.

Revision ID: 0006_phase3_generate
Revises: 0005_verum_jobs
Create Date: 2026-04-22
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0006_phase3_generate"
down_revision: Union[str, None] = "0005_verum_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "generations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "inference_id",
            UUID(as_uuid=True),
            sa.ForeignKey("inferences.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("error", sa.String(1024), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_generations_inference_id", "generations", ["inference_id"])

    op.create_table(
        "prompt_variants",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "generation_id",
            UUID(as_uuid=True),
            sa.ForeignKey("generations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("variant_type", sa.String(32), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("variables", JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_prompt_variants_generation_id", "prompt_variants", ["generation_id"])

    op.create_table(
        "rag_configs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "generation_id",
            UUID(as_uuid=True),
            sa.ForeignKey("generations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunking_strategy", sa.String(32), nullable=False, server_default="recursive"),
        sa.Column("chunk_size", sa.Integer, nullable=False, server_default="512"),
        sa.Column("chunk_overlap", sa.Integer, nullable=False, server_default="50"),
        sa.Column("top_k", sa.Integer, nullable=False, server_default="5"),
        sa.Column("hybrid_alpha", sa.Float, nullable=False, server_default="0.7"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "eval_pairs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "generation_id",
            UUID(as_uuid=True),
            sa.ForeignKey("generations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("query", sa.Text, nullable=False),
        sa.Column("expected_answer", sa.Text, nullable=False),
        sa.Column("context_needed", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_eval_pairs_generation_id", "eval_pairs", ["generation_id"])


def downgrade() -> None:
    op.drop_table("eval_pairs")
    op.drop_table("rag_configs")
    op.drop_table("prompt_variants")
    op.drop_table("generations")
```

- [ ] **Step 2: Apply the migration**

```bash
cd apps/api
alembic upgrade head
```

Expected: `Running upgrade 0005_verum_jobs -> 0006_phase3_generate, Phase 3 GENERATE tables`

- [ ] **Step 3: Pull Drizzle schema for dashboard**

```bash
cd apps/dashboard
pnpm drizzle-kit pull
```

Expected: `generations`, `prompt_variants`, `rag_configs`, `eval_pairs` appear in `src/lib/db/schema.ts`.

- [ ] **Step 4: Commit**

```bash
git add apps/api/alembic/versions/0006_phase3_generate.py apps/dashboard/src/lib/db/schema.ts
git commit -m "feat(generate): add Alembic migration for GENERATE stage tables"
```

---

## Task 2: SQLAlchemy ORM Model — Generation

**Files:**
- Create: `apps/api/src/db/models/generations.py`
- Modify: `apps/api/src/db/models/__init__.py`

- [ ] **Step 1: Create the model**

```python
# apps/api/src/db/models/generations.py
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class Generation(Base):
    __tablename__ = "generations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    inference_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inferences.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    error: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(tz=timezone.utc)
    )
```

- [ ] **Step 2: Register in `__init__.py`**

Replace the entire `apps/api/src/db/models/__init__.py`:

```python
from src.db.models.users import User
from src.db.models.repos import Repo
from src.db.models.generations import Generation

__all__ = ["User", "Repo", "Generation"]
```

- [ ] **Step 3: Commit**

```bash
git add apps/api/src/db/models/generations.py apps/api/src/db/models/__init__.py
git commit -m "feat(generate): add Generation SQLAlchemy model"
```

---

## Task 3: Pydantic Models — GenerateResult

**Files:**
- Create: `apps/api/src/loop/generate/__init__.py`
- Create: `apps/api/src/loop/generate/models.py`

- [ ] **Step 1: Create `__init__.py`**

```python
# apps/api/src/loop/generate/__init__.py
```

(Empty — just marks it as a package.)

- [ ] **Step 2: Create models**

```python
# apps/api/src/loop/generate/models.py
"""Pydantic models for the GENERATE stage."""
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

VARIANT_TYPES = ["original", "cot", "few_shot", "role_play", "concise"]


class PromptVariant(BaseModel):
    variant_type: str = Field(description=f"One of: {VARIANT_TYPES}")
    content: str = Field(description="Full prompt text with {variable} placeholders")
    variables: list[str] = Field(default_factory=list, description="Variable names found in content")


class RagConfig(BaseModel):
    chunking_strategy: str = Field(default="recursive", description="'recursive' or 'semantic'")
    chunk_size: int = Field(default=512, ge=128, le=2048)
    chunk_overlap: int = Field(default=50, ge=0, le=256)
    top_k: int = Field(default=5, ge=1, le=20)
    hybrid_alpha: float = Field(default=0.7, ge=0.0, le=1.0,
                                 description="Weight for vector vs text search (1.0 = vector only)")


class EvalPair(BaseModel):
    query: str = Field(description="Realistic user query")
    expected_answer: str = Field(description="Outline of correct answer")
    context_needed: bool = Field(default=True, description="Whether RAG context is required")


class GenerateResult(BaseModel):
    inference_id: UUID
    prompt_variants: list[PromptVariant]
    rag_config: RagConfig
    eval_pairs: list[EvalPair]
```

- [ ] **Step 3: Write failing test**

```python
# apps/api/tests/loop/generate/test_models.py
import pytest
from src.loop.generate.models import GenerateResult, PromptVariant, RagConfig, EvalPair
import uuid


def test_generate_result_round_trip():
    result = GenerateResult(
        inference_id=uuid.uuid4(),
        prompt_variants=[
            PromptVariant(variant_type="original", content="You are a tarot reader.", variables=[]),
            PromptVariant(variant_type="cot", content="Let's think step by step.", variables=[]),
        ],
        rag_config=RagConfig(chunking_strategy="semantic", chunk_size=512, top_k=5, hybrid_alpha=0.7),
        eval_pairs=[EvalPair(query="What does the Tower card mean?", expected_answer="Sudden change.", context_needed=True)],
    )
    dumped = result.model_dump()
    loaded = GenerateResult(**dumped)
    assert loaded.rag_config.chunking_strategy == "semantic"
    assert len(loaded.prompt_variants) == 2
```

- [ ] **Step 4: Run test — must pass (models only, no I/O)**

```bash
cd apps/api && python -m pytest tests/loop/generate/test_models.py -v
```

Expected: PASS (models are pure Pydantic, no side effects)

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/loop/generate/ apps/api/tests/loop/generate/
git commit -m "feat(generate): add Pydantic models for GenerateResult"
```

---

## Task 4: GENERATE Engine — 3 Claude API Calls

**Files:**
- Create: `apps/api/src/loop/generate/engine.py`

Context:
- `inference`: from `src.db.models.inferences.Inference` — has `.domain`, `.tone`, `.language`, `.user_type`, `.summary`
- `prompt_templates`: list of dicts with `{"content": str, "language": str, "variables": list[str]}`
- `sample_chunks`: list of str (top chunks from HARVEST, for context)
- Claude API pattern: same as `apps/api/src/loop/infer/engine.py` — `anthropic.AsyncAnthropic`, JSON response, strip markdown fences

- [ ] **Step 1: Write the engine**

```python
# apps/api/src/loop/generate/engine.py
"""GENERATE engine — 3 Claude Sonnet calls: variants → RAG config → eval pairs."""
from __future__ import annotations

import json
import os
import re
from typing import Any

import anthropic

import src.config as cfg
from src.loop.generate.models import EvalPair, GenerateResult, PromptVariant, RagConfig

_SYSTEM = "You are an expert prompt engineer and AI quality specialist. Respond ONLY with valid JSON. No markdown, no explanation."


def _parse_json(text: str) -> Any:
    """Strip optional markdown fences and parse JSON."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text.strip())


def _best_prompt(templates: list[dict[str, Any]]) -> str:
    """Pick the longest prompt template as the base for variant generation."""
    if not templates:
        return "(no prompt detected — generate a suitable system prompt for this service)"
    return max(templates, key=lambda t: len(t.get("content", "")))["content"]


async def _call_claude(client: anthropic.AsyncAnthropic, prompt: str) -> Any:
    msg = await client.messages.create(
        model=cfg.INFER_MODEL,
        max_tokens=cfg.GENERATE_MAX_TOKENS,
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = next((b.text for b in msg.content if hasattr(b, "text")), "{}")
    return _parse_json(raw)


async def run_generate(
    inference_id: str,
    domain: str,
    tone: str,
    language: str,
    user_type: str,
    summary: str,
    prompt_templates: list[dict[str, Any]],
    sample_chunks: list[str],
) -> GenerateResult:
    """Call Claude Sonnet 3 times to produce prompt variants, RAG config, and eval pairs."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")

    client = anthropic.AsyncAnthropic(api_key=api_key)
    base_prompt = _best_prompt(prompt_templates)
    chunks_preview = "\n---\n".join(sample_chunks[:5]) if sample_chunks else "(no chunks yet)"

    # ── Call 1: Generate 5 prompt variants ────────────────────────────────────
    variants_prompt = f"""SERVICE CONTEXT:
- Domain: {domain}
- Tone: {tone}
- Target users: {user_type}
- Language: {language}
- Summary: {summary}

ORIGINAL PROMPT:
{base_prompt}

Generate exactly 5 optimized variants of this prompt. Use {{variable}} for dynamic placeholders.
Respond as JSON:
{{
  "variants": [
    {{"variant_type": "original", "content": "...", "variables": []}},
    {{"variant_type": "cot", "content": "...", "variables": []}},
    {{"variant_type": "few_shot", "content": "...", "variables": []}},
    {{"variant_type": "role_play", "content": "...", "variables": []}},
    {{"variant_type": "concise", "content": "...", "variables": []}}
  ]
}}"""

    variants_data = await _call_claude(client, variants_prompt)
    prompt_variants = [
        PromptVariant(
            variant_type=v["variant_type"],
            content=v["content"],
            variables=v.get("variables", []),
        )
        for v in variants_data.get("variants", [])
    ]

    # ── Call 2: Recommend RAG config ───────────────────────────────────────────
    rag_prompt = f"""SERVICE: {domain} AI for {user_type} users.
SAMPLE KNOWLEDGE CHUNKS:
{chunks_preview}

Recommend optimal RAG retrieval config. Respond as JSON:
{{
  "chunking_strategy": "recursive",
  "chunk_size": 512,
  "chunk_overlap": 50,
  "top_k": 5,
  "hybrid_alpha": 0.7
}}
Rules: chunking_strategy must be "recursive" or "semantic"; chunk_size 128-1024; top_k 3-10; hybrid_alpha 0.0-1.0 (higher = more vector weight)."""

    rag_data = await _call_claude(client, rag_prompt)
    rag_config = RagConfig(
        chunking_strategy=rag_data.get("chunking_strategy", "recursive"),
        chunk_size=int(rag_data.get("chunk_size", 512)),
        chunk_overlap=int(rag_data.get("chunk_overlap", 50)),
        top_k=int(rag_data.get("top_k", 5)),
        hybrid_alpha=float(rag_data.get("hybrid_alpha", 0.7)),
    )

    # ── Call 3: Generate eval pairs ────────────────────────────────────────────
    eval_prompt = f"""You are testing a {domain} AI service for {user_type} users.
Service: {summary}

Sample knowledge:
{chunks_preview}

Generate 20 diverse test Q&A pairs. Include edge cases and common queries.
Respond as JSON:
{{
  "pairs": [
    {{"query": "...", "expected_answer": "...", "context_needed": true}}
  ]
}}"""

    eval_data = await _call_claude(client, eval_prompt)
    eval_pairs = [
        EvalPair(
            query=p["query"],
            expected_answer=p["expected_answer"],
            context_needed=bool(p.get("context_needed", True)),
        )
        for p in eval_data.get("pairs", [])
    ]

    import uuid as _uuid
    return GenerateResult(
        inference_id=_uuid.UUID(inference_id),
        prompt_variants=prompt_variants,
        rag_config=rag_config,
        eval_pairs=eval_pairs,
    )
```

- [ ] **Step 2: Add `GENERATE_MAX_TOKENS` to config**

Append to `apps/api/src/config.py`:

```python
# ── GENERATE stage ────────────────────────────────────────────────────────────
GENERATE_MAX_TOKENS: int = int(os.environ.get("GENERATE_MAX_TOKENS", "2048"))
```

- [ ] **Step 3: Write smoke test (mocked)**

```python
# apps/api/tests/loop/generate/test_engine.py
import json
import pytest
import respx
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from src.loop.generate.engine import _best_prompt, _parse_json, run_generate


def test_best_prompt_picks_longest():
    templates = [
        {"content": "short"},
        {"content": "a" * 200},
        {"content": "medium prompt here"},
    ]
    assert _best_prompt(templates) == "a" * 200


def test_best_prompt_empty_returns_fallback():
    result = _best_prompt([])
    assert "no prompt detected" in result


def test_parse_json_strips_fences():
    raw = '```json\n{"key": "value"}\n```'
    assert _parse_json(raw) == {"key": "value"}


def test_parse_json_plain():
    assert _parse_json('{"x": 1}') == {"x": 1}


@pytest.mark.asyncio
async def test_run_generate_calls_claude_three_times(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    call_count = 0

    async def fake_create(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            payload = {"variants": [
                {"variant_type": "original", "content": "You are helpful.", "variables": []},
                {"variant_type": "cot", "content": "Think step by step.", "variables": []},
                {"variant_type": "few_shot", "content": "Example:", "variables": []},
                {"variant_type": "role_play", "content": "You are a tarot master.", "variables": []},
                {"variant_type": "concise", "content": "Help.", "variables": []},
            ]}
        elif call_count == 2:
            payload = {"chunking_strategy": "semantic", "chunk_size": 512, "chunk_overlap": 50, "top_k": 5, "hybrid_alpha": 0.8}
        else:
            payload = {"pairs": [{"query": "What is tarot?", "expected_answer": "A card system.", "context_needed": True}]}

        mock = MagicMock()
        mock.content = [MagicMock(text=json.dumps(payload))]
        return mock

    with patch("anthropic.AsyncAnthropic") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(side_effect=fake_create)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        import uuid
        result = await run_generate(
            inference_id=str(uuid.uuid4()),
            domain="divination/tarot",
            tone="mystical",
            language="ko",
            user_type="consumer",
            summary="A tarot reading service.",
            prompt_templates=[{"content": "You are a tarot reader.", "variables": []}],
            sample_chunks=["The Tower card represents sudden change."],
        )

    assert call_count == 3
    assert len(result.prompt_variants) == 5
    assert result.rag_config.chunking_strategy == "semantic"
    assert len(result.eval_pairs) == 1
```

- [ ] **Step 4: Run tests**

```bash
cd apps/api && python -m pytest tests/loop/generate/ -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/loop/generate/engine.py apps/api/src/config.py apps/api/tests/loop/generate/test_engine.py
git commit -m "feat(generate): add GENERATE engine with 3 Claude API calls"
```

---

## Task 5: GENERATE Repository — DB I/O

**Files:**
- Create: `apps/api/src/loop/generate/repository.py`

- [ ] **Step 1: Write the repository**

```python
# apps/api/src/loop/generate/repository.py
"""Database I/O for the GENERATE stage."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.generations import Generation
from src.loop.generate.models import GenerateResult


async def create_pending_generation(
    db: AsyncSession,
    inference_id: uuid.UUID,
    generation_id: uuid.UUID,
) -> None:
    db.add(Generation(
        id=generation_id,
        inference_id=inference_id,
        status="pending",
        created_at=datetime.now(tz=timezone.utc),
    ))
    await db.flush()
    await db.commit()


async def save_generate_result(
    db: AsyncSession,
    generation_id: uuid.UUID,
    result: GenerateResult,
) -> None:
    stmt = select(Generation).where(Generation.id == generation_id)
    row = (await db.execute(stmt)).scalar_one()
    row.status = "done"
    row.generated_at = datetime.now(tz=timezone.utc)

    for variant in result.prompt_variants:
        await db.execute(
            text(
                "INSERT INTO prompt_variants (id, generation_id, variant_type, content, variables)"
                " VALUES (:id, :gid, :vtype, :content, :vars::jsonb)"
            ),
            {
                "id": str(uuid.uuid4()),
                "gid": str(generation_id),
                "vtype": variant.variant_type,
                "content": variant.content,
                "vars": str(variant.variables).replace("'", '"'),
            },
        )

    cfg = result.rag_config
    await db.execute(
        text(
            "INSERT INTO rag_configs (id, generation_id, chunking_strategy, chunk_size,"
            " chunk_overlap, top_k, hybrid_alpha)"
            " VALUES (:id, :gid, :strategy, :csize, :coverlap, :topk, :alpha)"
        ),
        {
            "id": str(uuid.uuid4()),
            "gid": str(generation_id),
            "strategy": cfg.chunking_strategy,
            "csize": cfg.chunk_size,
            "coverlap": cfg.chunk_overlap,
            "topk": cfg.top_k,
            "alpha": cfg.hybrid_alpha,
        },
    )

    for pair in result.eval_pairs:
        await db.execute(
            text(
                "INSERT INTO eval_pairs (id, generation_id, query, expected_answer, context_needed)"
                " VALUES (:id, :gid, :query, :answer, :ctx)"
            ),
            {
                "id": str(uuid.uuid4()),
                "gid": str(generation_id),
                "query": pair.query,
                "answer": pair.expected_answer,
                "ctx": pair.context_needed,
            },
        )

    await db.commit()


async def mark_generate_error(
    db: AsyncSession,
    generation_id: uuid.UUID,
    error: str,
) -> None:
    stmt = select(Generation).where(Generation.id == generation_id)
    row = (await db.execute(stmt)).scalar_one()
    row.status = "error"
    row.error = error[:1024]
    await db.commit()


async def get_generation_summary(
    db: AsyncSession,
    inference_id: uuid.UUID,
) -> dict[str, object] | None:
    """Return latest generation status + counts for a given inference."""
    result = await db.execute(
        text(
            "SELECT g.id, g.status, g.generated_at,"
            " (SELECT COUNT(*) FROM prompt_variants WHERE generation_id = g.id) AS variant_count,"
            " (SELECT COUNT(*) FROM eval_pairs WHERE generation_id = g.id) AS eval_count"
            " FROM generations g"
            " WHERE g.inference_id = :inf"
            " ORDER BY g.created_at DESC LIMIT 1"
        ),
        {"inf": str(inference_id)},
    )
    row = result.mappings().first()
    return dict(row) if row else None
```

- [ ] **Step 2: Commit**

```bash
git add apps/api/src/loop/generate/repository.py
git commit -m "feat(generate): add GENERATE repository (DB I/O)"
```

---

## Task 6: GENERATE Worker Handler

**Files:**
- Create: `apps/api/src/worker/handlers/generate.py`

- [ ] **Step 1: Write the handler**

```python
# apps/api/src/worker/handlers/generate.py
"""GENERATE job handler.

Payload schema:
  inference_id: str (UUID)
  generation_id: str (UUID)
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.inferences import Inference
from src.loop.generate.engine import run_generate
from src.loop.generate.repository import mark_generate_error, save_generate_result

logger = logging.getLogger(__name__)


async def handle_generate(
    db: AsyncSession,
    owner_user_id: uuid.UUID,
    payload: dict[str, Any],
) -> dict[str, Any]:
    inference_id = uuid.UUID(payload["inference_id"])
    generation_id = uuid.UUID(payload["generation_id"])

    # Load inference row (domain, tone, language, user_type, summary)
    inference = (
        await db.execute(select(Inference).where(Inference.id == inference_id))
    ).scalar_one_or_none()
    if inference is None:
        raise ValueError(f"Inference {inference_id} not found")

    # Load prompt templates from the analysis
    rows = (
        await db.execute(
            text(
                "SELECT prompt_templates FROM analyses WHERE id = :aid"
            ),
            {"aid": str(inference.analysis_id)},
        )
    ).fetchone()
    prompt_templates: list[dict[str, Any]] = (rows[0] or []) if rows else []

    # Get sample chunks from HARVEST (top 5 by any query)
    chunk_rows = (
        await db.execute(
            text(
                "SELECT content FROM chunks WHERE inference_id = :inf LIMIT 5"
            ),
            {"inf": str(inference_id)},
        )
    ).fetchall()
    sample_chunks = [r[0] for r in chunk_rows]

    try:
        result = await run_generate(
            inference_id=str(inference_id),
            domain=inference.domain or "other",
            tone=inference.tone or "professional",
            language=inference.language or "en",
            user_type=inference.user_type or "consumer",
            summary=inference.summary or "",
            prompt_templates=prompt_templates,
            sample_chunks=sample_chunks,
        )
        await save_generate_result(db, generation_id, result)

        logger.info(
            "GENERATE complete: %d variants, %d eval pairs for inference_id=%s",
            len(result.prompt_variants),
            len(result.eval_pairs),
            inference_id,
        )
        return {
            "generation_id": str(generation_id),
            "variant_count": len(result.prompt_variants),
            "eval_pair_count": len(result.eval_pairs),
            "rag_strategy": result.rag_config.chunking_strategy,
        }
    except Exception as exc:
        await mark_generate_error(db, generation_id, str(exc))
        raise
```

- [ ] **Step 2: Register handler in runner.py**

In `apps/api/src/worker/runner.py`, add the import and handler entry:

```python
# Add to imports at top:
from .handlers.generate import handle_generate

# Add to _HANDLERS dict:
_HANDLERS = {
    "analyze": handle_analyze,
    "infer": handle_infer,
    "harvest": handle_harvest,
    "retrieve": handle_retrieve,
    "generate": handle_generate,   # ← add this line
}
```

- [ ] **Step 3: Commit**

```bash
git add apps/api/src/worker/handlers/generate.py apps/api/src/worker/runner.py
git commit -m "feat(generate): add GENERATE worker handler and register in runner"
```

---

## Task 7: Chain HARVEST → GENERATE

**Files:**
- Modify: `apps/api/src/worker/handlers/harvest.py`

- [ ] **Step 1: Add the chain at end of handle_harvest**

Replace the full content of `apps/api/src/worker/handlers/harvest.py`:

```python
"""HARVEST job handler.

Payload schema:
  inference_id: str (UUID)
  source_ids: list of [source_id_str, url_str] pairs
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.loop.harvest.pipeline import harvest_source
from src.worker.chain import enqueue_next

logger = logging.getLogger(__name__)


async def handle_harvest(
    db: AsyncSession,
    owner_user_id: uuid.UUID,
    payload: dict[str, Any],
) -> dict[str, Any]:
    inference_id = uuid.UUID(payload["inference_id"])
    source_pairs: list[list[str]] = payload["source_ids"]  # [[source_id, url], ...]

    total_chunks = 0
    results: list[dict[str, Any]] = []
    for source_id_str, url in source_pairs:
        source_id = uuid.UUID(source_id_str)
        try:
            count = await harvest_source(db, source_id, url, inference_id)
            total_chunks += count
            results.append({"source_id": source_id_str, "chunks": count, "status": "done"})
        except Exception as exc:
            results.append({"source_id": source_id_str, "error": str(exc), "status": "error"})

    # Chain HARVEST → GENERATE
    generation_id = uuid.uuid4()
    from sqlalchemy import text
    await db.execute(
        text(
            "INSERT INTO generations (id, inference_id, status)"
            " VALUES (:id, :inf, 'pending')"
        ),
        {"id": str(generation_id), "inf": str(inference_id)},
    )
    await enqueue_next(
        db,
        kind="generate",
        payload={"inference_id": str(inference_id), "generation_id": str(generation_id)},
        owner_user_id=owner_user_id,
    )
    await db.commit()

    logger.info(
        "HARVEST→GENERATE chain: enqueued generation_id=%s for inference_id=%s",
        generation_id,
        inference_id,
    )

    return {
        "inference_id": str(inference_id),
        "total_chunks": total_chunks,
        "sources": results,
    }
```

- [ ] **Step 2: Commit**

```bash
git add apps/api/src/worker/handlers/harvest.py
git commit -m "feat(generate): chain HARVEST→GENERATE automatically after harvest completes"
```

---

## Task 8: Semantic Chunking

**Files:**
- Modify: `apps/api/src/loop/harvest/chunker.py`
- Modify: `apps/api/src/loop/harvest/pipeline.py`

- [ ] **Step 1: Add `semantic_split()` to chunker.py**

Append to the end of `apps/api/src/loop/harvest/chunker.py`:

```python
_SENTENCE_ENDINGS = re.compile(r'(?<=[.!?])\s+')


def semantic_split(
    text: str,
    chunk_size: int = 512,
    overlap: int = 50,
) -> list[str]:
    """Split text at sentence boundaries, grouping sentences until chunk_size.

    Overlap is applied by repeating the tail of the previous chunk.
    Fallback: if no sentence boundaries found, delegates to recursive_split.
    """
    import re as _re
    sentences = _re.split(r'(?<=[.!?])\s+', text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]

    if len(sentences) <= 1:
        return recursive_split(text, chunk_size=chunk_size, overlap=overlap)

    chunks: list[str] = []
    current_sentences: list[str] = []
    current_len = 0

    for sentence in sentences:
        if current_len + len(sentence) + 1 > chunk_size and current_sentences:
            chunk = " ".join(current_sentences)
            chunks.append(chunk)
            # Keep last sentence as overlap seed
            tail = current_sentences[-1] if len(current_sentences[-1]) <= overlap else current_sentences[-1][-overlap:]
            current_sentences = [tail, sentence]
            current_len = len(tail) + len(sentence) + 1
        else:
            current_sentences.append(sentence)
            current_len += len(sentence) + 1

    if current_sentences:
        chunks.append(" ".join(current_sentences))

    return [c for c in chunks if c.strip()]
```

Also add `import re` at the top of `chunker.py` (after `from __future__ import annotations`):

```python
import re
```

- [ ] **Step 2: Write test**

```python
# Append to apps/api/tests/loop/harvest/test_chunker.py
from src.loop.harvest.chunker import semantic_split

def test_semantic_split_basic():
    text = "The Tower card means sudden change. It often signals upheaval. Reversed, it suggests resistance to change."
    chunks = semantic_split(text, chunk_size=80, overlap=20)
    assert len(chunks) >= 1
    assert all(isinstance(c, str) for c in chunks)
    assert all(c.strip() for c in chunks)

def test_semantic_split_short_text_no_split():
    text = "Short sentence."
    chunks = semantic_split(text, chunk_size=512, overlap=50)
    assert len(chunks) == 1
    assert chunks[0] == "Short sentence."
```

- [ ] **Step 3: Run test**

```bash
cd apps/api && python -m pytest tests/loop/harvest/test_chunker.py -v
```

Expected: all tests PASS including new semantic ones

- [ ] **Step 4: Commit**

```bash
git add apps/api/src/loop/harvest/chunker.py apps/api/tests/loop/harvest/test_chunker.py
git commit -m "feat(harvest): add sentence-boundary semantic_split() to chunker"
```

---

## Task 9: Dashboard — Add GENERATE to RepoStatus

**Files:**
- Modify: `apps/dashboard/src/lib/db/queries.ts`

- [ ] **Step 1: Add generation query and update RepoStatus interface**

In `apps/dashboard/src/lib/db/queries.ts`, add after the `RepoStatus` interface definition:

```typescript
export interface GenerationSummary {
  id: string;
  status: string;
  generated_at: string | null;
  variant_count: number;
  eval_count: number;
}

export interface RepoStatus {
  repo: Repo;
  latestAnalysis: Analysis | null;
  latestInference: Inference | null;
  harvestChunks: number;
  harvestSourcesDone: number;
  harvestSourcesTotal: number;
  latestGeneration: GenerationSummary | null;  // ← add
}
```

Then add a helper function before `getRepoStatus`:

```typescript
async function getLatestGenerationSummary(inferenceId: string): Promise<GenerationSummary | null> {
  const rows = await db.execute(
    sql`SELECT g.id::text, g.status, g.generated_at::text,
        (SELECT COUNT(*)::int FROM prompt_variants WHERE generation_id = g.id) AS variant_count,
        (SELECT COUNT(*)::int FROM eval_pairs WHERE generation_id = g.id) AS eval_count
        FROM generations g
        WHERE g.inference_id = ${inferenceId}::uuid
        ORDER BY g.created_at DESC LIMIT 1`,
  );
  const row = rows.rows[0] as GenerationSummary | undefined;
  return row ?? null;
}
```

And update `getRepoStatus` to include it:

```typescript
  let latestGeneration: GenerationSummary | null = null;
  if (latestInference?.status === "done") {
    latestGeneration = await getLatestGenerationSummary(latestInference.id);
  }

  return {
    repo,
    latestAnalysis,
    latestInference,
    harvestChunks,
    harvestSourcesDone,
    harvestSourcesTotal,
    latestGeneration,   // ← add
  };
```

- [ ] **Step 2: Update the status API route response**

`apps/dashboard/src/app/api/repos/[id]/status/route.ts` already returns the full object from `getRepoStatus`, so no change needed.

- [ ] **Step 3: Build check**

```bash
cd apps/dashboard && pnpm tsc --noEmit
```

Expected: 0 errors

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/src/lib/db/queries.ts
git commit -m "feat(generate): add latestGeneration to RepoStatus query"
```

---

## Task 10: Dashboard StagesView — Add [4] GENERATE Section

**Files:**
- Modify: `apps/dashboard/src/app/repos/[id]/StagesView.tsx`
- Modify: `apps/dashboard/src/app/repos/[id]/actions.ts`

- [ ] **Step 1: Add `rerunGenerate` to actions.ts**

Append to `apps/dashboard/src/app/repos/[id]/actions.ts`:

```typescript
export async function rerunGenerate(inferenceId: string) {
  "use server";
  const session = await auth();
  if (!session?.user) throw new Error("unauthorized");
  const uid = String((session.user as Record<string, unknown>).id ?? "");

  // Create a new pending generation and enqueue
  const { db } = await import("@/lib/db/client");
  const { sql } = await import("drizzle-orm");
  const generationId = crypto.randomUUID();
  await db.execute(
    sql`INSERT INTO generations (id, inference_id, status) VALUES (${generationId}::uuid, ${inferenceId}::uuid, 'pending')`
  );
  await db.execute(
    sql`INSERT INTO verum_jobs (kind, payload, owner_user_id, status)
        VALUES ('generate', ${JSON.stringify({ inference_id: inferenceId, generation_id: generationId })}::jsonb, ${uid}::uuid, 'queued')`
  );
}
```

- [ ] **Step 2: Add [4] GENERATE section to StagesView.tsx**

In `StagesView.tsx`, destructure `latestGeneration` and add a new section between HARVEST and RETRIEVE:

After the line:
```typescript
const { repo, latestAnalysis, latestInference, harvestChunks, harvestSourcesDone, harvestSourcesTotal } = status;
```

Change to:
```typescript
const { repo, latestAnalysis, latestInference, harvestChunks, harvestSourcesDone, harvestSourcesTotal, latestGeneration } = status;
```

After the `{/* ── HARVEST ── */}` section closing `</Section>`, add:

```tsx
{/* ── GENERATE ── */}
<Section title="[4] GENERATE" color="#dc2626">
  {latestGeneration ? (
    <div>
      <StatusRow
        label="Status"
        value={isRunning(latestGeneration.status) ? `${latestGeneration.status} (running...)` : latestGeneration.status}
      />
      {latestGeneration.status === "done" && (
        <>
          <StatusRow label="Prompt variants" value={String(latestGeneration.variant_count)} />
          <StatusRow label="Eval pairs" value={String(latestGeneration.eval_count)} />
        </>
      )}
    </div>
  ) : (
    <p style={{ color: "#888", fontSize: 13 }}>
      {harvestChunks > 0 ? "Generate in progress or not started." : "Complete HARVEST first."}
    </p>
  )}
  {latestInference?.status === "done" && harvestChunks > 0 && (
    <form action={rerunGenerate.bind(null, latestInference.id)} style={{ marginTop: 12 }}>
      <button type="submit" style={{ ...btnStyle, background: "#dc2626" }}>
        {latestGeneration ? "Re-run GENERATE" : "Run GENERATE"}
      </button>
    </form>
  )}
</Section>
```

Also import `rerunGenerate` at the top:
```typescript
import { rerunAnalyze, rerunInfer, rerunHarvest, rerunGenerate } from "./actions";
```

- [ ] **Step 3: Build check**

```bash
cd apps/dashboard && pnpm build 2>&1 | tail -20
```

Expected: build completes with no type errors

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/src/app/repos/[id]/StagesView.tsx apps/dashboard/src/app/repos/[id]/actions.ts
git commit -m "feat(generate): add [4] GENERATE section to StagesView with re-run button"
```

---

## Task 11: Fix README Embedding Reference

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Fix tech stack line**

In `README.md`, replace the AI line:

```markdown
**AI** — Claude Sonnet 4.6 (INFER), OpenAI `text-embedding-3-small` (embeddings)
```

with:

```markdown
**AI** — Claude Sonnet 4.6 (INFER + GENERATE), Voyage AI `voyage-3.5` (embeddings, 1024-dim)
```

Apply the same fix in `README.ko.md`:

```markdown
**AI** — Claude Sonnet 4.6 (INFER + GENERATE), Voyage AI `voyage-3.5` (임베딩, 1024차원)
```

- [ ] **Step 2: Commit**

```bash
git add README.md README.ko.md
git commit -m "docs: fix embedding provider reference (Voyage AI, not OpenAI)"
```

---

## Task 12: Deploy + Verify

- [ ] **Step 1: Run full Python test suite**

```bash
cd apps/api && python -m pytest tests/ -v --tb=short
```

Expected: all tests PASS

- [ ] **Step 2: Build dashboard**

```bash
cd apps/dashboard && pnpm build
```

Expected: build completes with 0 errors

- [ ] **Step 3: Run Docker health check**

```bash
make docker-healthcheck
```

Expected: `{"status":"ok"}` from `/health`

- [ ] **Step 4: Push to origin**

```bash
git push origin main
```

- [ ] **Step 5: Verify on Railway**
  - Check deployment logs: `Claiming job ... kind=generate` appears after HARVEST completes
  - Re-register ArcanaInsight Repo → wait ~3 minutes → `/repos/{id}` should show [4] GENERATE: done, 5 variants, 20 eval pairs

- [ ] **Step 6: Update ROADMAP.md**

Mark F-3.1, F-3.2, F-3.3 as `✅` in `docs/ROADMAP.md`.

```bash
git add docs/ROADMAP.md
git commit -m "docs: mark GENERATE deliverables F-3.1/3.2/3.3 complete in ROADMAP"
```

---

## Self-Review Checklist

- [x] Alembic migration covers all 4 tables with FKs and indexes
- [x] `down_revision` points to `0005_verum_jobs`
- [x] Pydantic models used consistently — `GenerateResult.rag_config` is `RagConfig` in engine and repository
- [x] `GENERATE_MAX_TOKENS` added to config.py before engine.py uses it
- [x] `handle_generate` registered in `runner.py` `_HANDLERS`
- [x] HARVEST handler chains to GENERATE (inserts pending generation row first)
- [x] `rerunGenerate` in actions.ts inserts both `generations` row and `verum_jobs` row
- [x] Dashboard `latestGeneration` typed as `GenerationSummary | null` — StagesView handles null gracefully
- [x] README.md and README.ko.md both updated with Voyage AI fix
