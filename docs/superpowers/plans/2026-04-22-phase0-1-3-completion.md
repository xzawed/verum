# Phase 0 / Phase 1 / Phase 3 Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete all remaining deliverables for Phase 0 (F-0.7), Phase 1 (F-1.4, F-1.8), and Phase 3 (F-3.4 through F-3.10), ending with ArcanaInsight running on Verum-generated prompts and RAG.

**Architecture:** Phase order is strictly respected — each batch runs to completion before the next. Batches 1b+1b, 2a+2b, 4a+4b contain independent tasks that can be parallelized. All public HTTP is served by Next.js (App Router API routes). Python worker runs as asyncio subprocess consuming `verum_jobs`. SDK communicates with the `/api/v1/deploy/[id]/config` endpoint only (no LLM proxy).

**Tech Stack:** Python 3.13 + SQLAlchemy 2 + Alembic (DB schema SoT), Next.js 16 App Router + Drizzle ORM (read/write from Node), TypeScript strict, pytest + pytest-asyncio, Jest.

---

## File Map

### Batch 0 — CI
- Modify: `.github/workflows/ci.yml`

### Batch 1 — Phase 1
- Create: `apps/dashboard/src/app/api/v1/analyze/route.ts`
- Create: `apps/dashboard/src/app/api/v1/analyze/[id]/route.ts`
- Create: `apps/dashboard/src/app/api/v1/infer/route.ts`
- Create: `apps/dashboard/src/app/api/v1/infer/[id]/route.ts`
- Create: `docs/WEEKLY.md`

### Batch 2 — GENERATE (F-3.4 + F-3.5)
- Create: `apps/api/src/loop/generate/metric_profile.py`
- Create: `apps/api/tests/loop/generate/test_metric_profile.py`
- Create: `apps/api/alembic/versions/0008_metric_profile_deployments.py`
- Modify: `apps/api/src/db/models/generations.py`
- Modify: `apps/api/src/loop/generate/models.py`
- Modify: `apps/api/src/loop/generate/engine.py`
- Modify: `apps/api/src/loop/generate/repository.py`
- Modify: `apps/dashboard/src/lib/db/schema.ts`
- Modify: `apps/dashboard/src/lib/db/jobs.ts`
- Modify: `apps/dashboard/src/lib/db/queries.ts`
- Create: `apps/dashboard/src/app/api/v1/generate/route.ts`
- Create: `apps/dashboard/src/app/api/v1/generate/[id]/route.ts`
- Create: `apps/dashboard/src/app/api/v1/generate/[id]/approve/route.ts`
- Create: `apps/dashboard/src/app/generate/[inference_id]/page.tsx`

### Batch 3 — DEPLOY (F-3.6 + F-3.7)
- Create: `apps/api/src/loop/deploy/__init__.py`
- Create: `apps/api/src/loop/deploy/models.py`
- Create: `apps/api/src/loop/deploy/engine.py`
- Create: `apps/api/src/loop/deploy/repository.py`
- Create: `apps/api/src/worker/handlers/deploy.py`
- Modify: `apps/api/src/worker/runner.py`
- Create: `apps/api/tests/loop/deploy/__init__.py`
- Create: `apps/api/tests/loop/deploy/test_engine.py`
- Create: `apps/dashboard/src/app/api/v1/deploy/route.ts`
- Create: `apps/dashboard/src/app/api/v1/deploy/[id]/route.ts`
- Create: `apps/dashboard/src/app/api/v1/deploy/[id]/traffic/route.ts`
- Create: `apps/dashboard/src/app/api/v1/deploy/[id]/rollback/route.ts`
- Create: `apps/dashboard/src/app/api/v1/deploy/[id]/config/route.ts`
- Create: `apps/dashboard/src/app/deploy/[id]/page.tsx`

### Batch 4 — SDKs (F-3.8 + F-3.9)
- Create: `packages/sdk-python/src/verum/client.py`
- Create: `packages/sdk-python/src/verum/_cache.py`
- Create: `packages/sdk-python/src/verum/_router.py`
- Modify: `packages/sdk-python/src/verum/__init__.py`
- Create: `packages/sdk-python/tests/__init__.py`
- Create: `packages/sdk-python/tests/test_client.py`
- Modify: `packages/sdk-typescript/src/index.ts`
- Create: `packages/sdk-typescript/src/client.ts`
- Create: `packages/sdk-typescript/src/cache.ts`
- Create: `packages/sdk-typescript/src/router.ts`
- Create: `packages/sdk-typescript/tests/client.test.ts`

### Batch 5 — ArcanaInsight Integration (F-3.10)
- Create: `examples/arcana-integration/README.md`
- Create: `examples/arcana-integration/before.py`
- Create: `examples/arcana-integration/after.py`
- Create: `examples/arcana-integration/.env.example`

---

## Task 1: Batch 0 — CI Fix (F-0.7)

**Files:**
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Fix pip install path and add pylint**

In `.github/workflows/ci.yml`, make these changes:

In the `lint-python` job, change:
```yaml
      - name: Install API + dev deps
        run: pip install "apps/api[dev]"
```
to:
```yaml
      - name: Install API + dev deps
        run: pip install -e "./apps/api[dev]"
```

Then add pylint step after the `bandit` step:
```yaml
      - name: pylint
        run: pylint apps/api/src --fail-under=8.0
```

In the `test-api` job, apply the same path fix:
```yaml
      - name: Install API + dev deps
        run: pip install -e "./apps/api[dev]"
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "fix(ci): fix pip editable install path and add pylint step"
```

---

## Task 2: Batch 1a — ArcanaInsight ANALYZE Validation (F-1.4)

**Files:**
- Create: `docs/WEEKLY.md`
- Modify: `docs/ROADMAP.md`

- [ ] **Step 1: Run ANALYZE against ArcanaInsight**

```bash
cd apps/api
DATABASE_URL=postgresql+asyncpg://verum:verum@localhost:5432/verum \
PYTHONPATH=. \
python -m src.loop.analyze.cli \
  --repo https://github.com/xzawed/ArcanaInsight \
  --branch main \
  > /tmp/arcana-result.json
cat /tmp/arcana-result.json
```

- [ ] **Step 2: Verify assertions**

```bash
python - <<'EOF'
import json, sys
data = json.load(open("/tmp/arcana-result.json"))
sites = data.get("call_sites", [])
print(f"call_sites: {len(sites)}")
grok_sites = [s for s in sites if s.get("sdk") == "grok"]
print(f"grok sites: {len(grok_sites)}")
for s in sites[:3]:
    print(f"  {s['file_path']}:{s['line']} sdk={s['sdk']}")
assert len(sites) >= 1, "No call_sites found"
assert len(grok_sites) >= 1, "No grok SDK sites found"
assert all(s.get("file_path") and s.get("line") for s in sites), "Missing file_path or line"
print("PASS")
EOF
```

Expected output: `PASS` with at least 1 grok call site.

- [ ] **Step 3: Document results in WEEKLY.md**

Create `docs/WEEKLY.md`:

```markdown
# Verum Weekly Log

## 2026-04-22 — Phase 1 Completion

### ArcanaInsight ANALYZE Validation (F-1.4)

Run: `python -m src.loop.analyze.cli --repo https://github.com/xzawed/ArcanaInsight --branch main`

Results:
- call_sites detected: [fill in from output]
- grok SDK sites: [fill in from output]
- Sample: [paste first call site here]
- Wall clock: [fill in]

Status: ✅ Phase 1 completion gate passed
```

- [ ] **Step 4: Update ROADMAP.md**

In `docs/ROADMAP.md`, change F-1.4 status from `🚧` to `✅`.

- [ ] **Step 5: Commit**

```bash
git add docs/WEEKLY.md docs/ROADMAP.md
git commit -m "docs(analyze): F-1.4 ArcanaInsight ANALYZE validation results"
```

---

## Task 3: Batch 1b — REST Endpoints (F-1.8)

**Files:**
- Create: `apps/dashboard/src/app/api/v1/analyze/route.ts`
- Create: `apps/dashboard/src/app/api/v1/analyze/[id]/route.ts`
- Create: `apps/dashboard/src/app/api/v1/infer/route.ts`
- Create: `apps/dashboard/src/app/api/v1/infer/[id]/route.ts`

- [ ] **Step 1: Create analyze POST route**

Create `apps/dashboard/src/app/api/v1/analyze/route.ts`:

```typescript
import { auth } from "@/auth";
import { enqueueAnalyze, getRepo } from "@/lib/db/jobs";
import { getRepo as queryRepo } from "@/lib/db/queries";

export async function POST(req: Request) {
  const session = await auth();
  if (!session?.user) return new Response("unauthorized", { status: 401 });
  const uid = String((session.user as Record<string, unknown>).id ?? "");
  if (!uid) return new Response("unauthorized", { status: 401 });

  const body = await req.json() as { repo_id: string; branch?: string };
  if (!body.repo_id) return new Response("repo_id required", { status: 400 });

  const repo = await queryRepo(uid, body.repo_id);
  if (!repo) return new Response("not found", { status: 404 });

  const analysis = await enqueueAnalyze({
    userId: uid,
    repoId: repo.id,
    repoUrl: repo.github_url,
    branch: body.branch ?? repo.default_branch,
  });

  return Response.json({ job_id: analysis.id }, { status: 202 });
}
```

- [ ] **Step 2: Create analyze GET route**

Create `apps/dashboard/src/app/api/v1/analyze/[id]/route.ts`:

```typescript
import { auth } from "@/auth";
import { getAnalysis } from "@/lib/db/queries";

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const session = await auth();
  if (!session?.user) return new Response("unauthorized", { status: 401 });
  const uid = String((session.user as Record<string, unknown>).id ?? "");
  if (!uid) return new Response("unauthorized", { status: 401 });

  const { id } = await params;
  const analysis = await getAnalysis(uid, id);
  if (!analysis) return new Response("not found", { status: 404 });

  return Response.json(analysis, { headers: { "Cache-Control": "no-store" } });
}
```

- [ ] **Step 3: Create infer POST route**

Create `apps/dashboard/src/app/api/v1/infer/route.ts`:

```typescript
import { auth } from "@/auth";
import { enqueueInfer } from "@/lib/db/jobs";
import { getAnalysis } from "@/lib/db/queries";

export async function POST(req: Request) {
  const session = await auth();
  if (!session?.user) return new Response("unauthorized", { status: 401 });
  const uid = String((session.user as Record<string, unknown>).id ?? "");
  if (!uid) return new Response("unauthorized", { status: 401 });

  const body = await req.json() as { analysis_id: string; repo_id: string };
  if (!body.analysis_id || !body.repo_id) {
    return new Response("analysis_id and repo_id required", { status: 400 });
  }

  const analysis = await getAnalysis(uid, body.analysis_id);
  if (!analysis) return new Response("not found", { status: 404 });

  const inference = await enqueueInfer({
    userId: uid,
    repoId: body.repo_id,
    analysisId: body.analysis_id,
  });

  return Response.json({ job_id: inference.id }, { status: 202 });
}
```

- [ ] **Step 4: Create infer GET route**

Create `apps/dashboard/src/app/api/v1/infer/[id]/route.ts`:

```typescript
import { auth } from "@/auth";
import { getInference } from "@/lib/db/queries";

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const session = await auth();
  if (!session?.user) return new Response("unauthorized", { status: 401 });
  const uid = String((session.user as Record<string, unknown>).id ?? "");
  if (!uid) return new Response("unauthorized", { status: 401 });

  const { id } = await params;
  const inference = await getInference(uid, id);
  if (!inference) return new Response("not found", { status: 404 });

  return Response.json(inference, { headers: { "Cache-Control": "no-store" } });
}
```

- [ ] **Step 5: Update ROADMAP.md**

Change F-1.8 status to ✅.

- [ ] **Step 6: Commit**

```bash
git add apps/dashboard/src/app/api/v1/ docs/ROADMAP.md
git commit -m "feat(api): F-1.8 expose /api/v1/analyze and /api/v1/infer REST endpoints"
```

---

## Task 4: Metric Profile — Python (F-3.4)

**Files:**
- Create: `apps/api/src/loop/generate/metric_profile.py`
- Create: `apps/api/tests/loop/generate/test_metric_profile.py`
- Create: `apps/api/alembic/versions/0008_metric_profile_deployments.py`
- Modify: `apps/api/src/db/models/generations.py`
- Modify: `apps/api/src/loop/generate/models.py`
- Modify: `apps/api/src/loop/generate/engine.py`
- Modify: `apps/api/src/loop/generate/repository.py`

- [ ] **Step 1: Write failing test**

Create `apps/api/tests/loop/generate/test_metric_profile.py`:

```python
import pytest
from src.loop.generate.metric_profile import MetricProfile, select_metric_profile


def test_consumer_divination_primary():
    profile = select_metric_profile("consumer", "divination/tarot")
    assert "latency_p95" in profile.primary_metrics
    assert "user_satisfaction" in profile.primary_metrics
    assert "response_length" in profile.primary_metrics
    assert profile.profile_name == "consumer-divination"


def test_developer_code_review():
    profile = select_metric_profile("developer", "code_review")
    assert "accuracy" in profile.primary_metrics
    assert "cost_per_call" in profile.primary_metrics
    assert profile.profile_name == "developer-code_review"


def test_enterprise():
    profile = select_metric_profile("enterprise", "legal_qa")
    assert "cost_per_call" in profile.primary_metrics
    assert "reliability" in profile.primary_metrics
    assert profile.profile_name == "enterprise-legal_qa"


def test_unknown_user_type_defaults_to_consumer():
    profile = select_metric_profile("unknown_type", "other")
    assert len(profile.primary_metrics) >= 2
    assert isinstance(profile.profile_name, str)


def test_metric_profile_is_pydantic():
    profile = select_metric_profile("consumer", "divination/tarot")
    assert isinstance(profile, MetricProfile)
    data = profile.model_dump()
    assert "primary_metrics" in data
    assert "secondary_metrics" in data
    assert "profile_name" in data
```

- [ ] **Step 2: Run to verify failure**

```bash
cd apps/api
PYTHONPATH=. pytest tests/loop/generate/test_metric_profile.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.loop.generate.metric_profile'`

- [ ] **Step 3: Implement metric_profile.py**

Create `apps/api/src/loop/generate/metric_profile.py`:

```python
"""Metric profile auto-selection for the GENERATE stage ([4] of The Verum Loop).

Pure function — no LLM call, no DB I/O. Selects dashboard metrics based on
the service's user_type and domain inferred in the INFER stage.
"""
from __future__ import annotations

from pydantic import BaseModel


class MetricProfile(BaseModel):
    primary_metrics: list[str]
    secondary_metrics: list[str]
    profile_name: str


_CONSUMER_PRIMARY = ["latency_p95", "user_satisfaction", "response_length"]
_CONSUMER_SECONDARY = ["cost_per_call", "error_rate"]

_DEVELOPER_PRIMARY = ["accuracy", "latency_p95", "cost_per_call"]
_DEVELOPER_SECONDARY = ["token_count", "error_rate"]

_ENTERPRISE_PRIMARY = ["cost_per_call", "reliability", "throughput"]
_ENTERPRISE_SECONDARY = ["latency_p95", "error_rate"]


def select_metric_profile(user_type: str, domain: str) -> MetricProfile:
    """Return the recommended dashboard metric profile for this service.

    Args:
        user_type: From ServiceInference — "consumer", "developer", or "enterprise".
        domain: From ServiceInference — e.g. "divination/tarot", "code_review".

    Returns:
        MetricProfile with primary and secondary metric lists and a profile name.
    """
    domain_key = domain.split("/")[0] if "/" in domain else domain

    if user_type == "developer":
        primary = list(_DEVELOPER_PRIMARY)
        secondary = list(_DEVELOPER_SECONDARY)
    elif user_type == "enterprise":
        primary = list(_ENTERPRISE_PRIMARY)
        secondary = list(_ENTERPRISE_SECONDARY)
    else:
        primary = list(_CONSUMER_PRIMARY)
        secondary = list(_CONSUMER_SECONDARY)

    if domain_key == "divination" and "response_length" not in primary:
        primary.append("response_length")

    return MetricProfile(
        primary_metrics=primary,
        secondary_metrics=secondary,
        profile_name=f"{user_type}-{domain_key}",
    )
```

- [ ] **Step 4: Run tests to verify pass**

```bash
cd apps/api
PYTHONPATH=. pytest tests/loop/generate/test_metric_profile.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Add MetricProfile to GenerateResult**

In `apps/api/src/loop/generate/models.py`, add import and field:

```python
from src.loop.generate.metric_profile import MetricProfile  # add this import

class GenerateResult(BaseModel):
    inference_id: UUID
    prompt_variants: list[PromptVariant]
    rag_config: RagConfig
    eval_pairs: list[EvalPair]
    metric_profile: MetricProfile | None = None   # add this field
```

- [ ] **Step 6: Wire metric_profile into engine.py**

In `apps/api/src/loop/generate/engine.py`, add import and populate the field at the end of `run_generate`:

```python
from src.loop.generate.metric_profile import select_metric_profile  # add import

# Inside run_generate(), update the return statement:
    metric_profile = select_metric_profile(user_type, domain)

    return GenerateResult(
        inference_id=uuid.UUID(inference_id),
        prompt_variants=prompt_variants,
        rag_config=rag_config,
        eval_pairs=eval_pairs,
        metric_profile=metric_profile,
    )
```

- [ ] **Step 7: Add metric_profile column to Generation SQLAlchemy model**

In `apps/api/src/db/models/generations.py`, add:

```python
from sqlalchemy.dialects.postgresql import JSONB, UUID  # add JSONB

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
    metric_profile: Mapped[dict | None] = mapped_column(JSONB, nullable=True)   # new
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(tz=timezone.utc)
    )
```

- [ ] **Step 8: Persist metric_profile in repository.py**

In `apps/api/src/loop/generate/repository.py`, update `save_generate_result` to save metric_profile:

```python
# Inside save_generate_result(), after setting row.status = "done":
    if result.metric_profile is not None:
        row.metric_profile = result.metric_profile.model_dump()
```

- [ ] **Step 9: Create Alembic migration**

Create `apps/api/alembic/versions/0008_metric_profile_deployments.py`:

```python
"""Add metric_profile to generations; create deployments table.

Revision ID: 0008_metric_profile_deployments
Revises: 0007_rag_configs_unique
Create Date: 2026-04-22
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0008_metric_profile_deployments"
down_revision: Union[str, None] = "0007_rag_configs_unique"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("generations", sa.Column("metric_profile", JSONB, nullable=True))

    op.create_table(
        "deployments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "generation_id",
            UUID(as_uuid=True),
            sa.ForeignKey("generations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(32), nullable=False, server_default="canary"),
        sa.Column(
            "traffic_split",
            JSONB,
            nullable=False,
            server_default='{"baseline": 0.9, "variant": 0.1}',
        ),
        sa.Column("error_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_calls", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_deployments_generation_id", "deployments", ["generation_id"])


def downgrade() -> None:
    op.drop_table("deployments")
    op.drop_column("generations", "metric_profile")
```

- [ ] **Step 10: Run migration**

```bash
cd apps/api
DATABASE_URL=postgresql+asyncpg://verum:verum@localhost:5432/verum \
alembic upgrade head
```

Expected: `Running upgrade 0007_rag_configs_unique -> 0008_metric_profile_deployments, ...`

- [ ] **Step 11: Run full generate tests**

```bash
cd apps/api
PYTHONPATH=. pytest tests/loop/generate/ -v
```

Expected: all tests pass.

- [ ] **Step 12: Commit**

```bash
git add apps/api/src/loop/generate/metric_profile.py \
        apps/api/src/loop/generate/models.py \
        apps/api/src/loop/generate/engine.py \
        apps/api/src/loop/generate/repository.py \
        apps/api/src/db/models/generations.py \
        apps/api/alembic/versions/0008_metric_profile_deployments.py \
        apps/api/tests/loop/generate/test_metric_profile.py
git commit -m "feat(generate): F-3.4 metric profile auto-selection + deployments migration"
```

---

## Task 5: GENERATE API + Dashboard UI (F-3.5)

**Files:**
- Modify: `apps/dashboard/src/lib/db/schema.ts`
- Modify: `apps/dashboard/src/lib/db/jobs.ts`
- Modify: `apps/dashboard/src/lib/db/queries.ts`
- Create: `apps/dashboard/src/app/api/v1/generate/route.ts`
- Create: `apps/dashboard/src/app/api/v1/generate/[id]/route.ts`
- Create: `apps/dashboard/src/app/api/v1/generate/[id]/approve/route.ts`
- Create: `apps/dashboard/src/app/generate/[inference_id]/page.tsx`

- [ ] **Step 1: Update schema.ts — add metric_profile + deployments**

In `apps/dashboard/src/lib/db/schema.ts`:

Add `metric_profile` to the `generations` table definition:
```typescript
export const generations = pgTable("generations", {
  id: uuid("id").primaryKey().$defaultFn(() => crypto.randomUUID()),
  inference_id: uuid("inference_id")
    .notNull()
    .references(() => inferences.id, { onDelete: "cascade" }),
  status: varchar("status", { length: 32 }).notNull().default("pending"),
  error: varchar("error", { length: 1024 }),
  metric_profile: jsonb("metric_profile"),   // add this line
  generated_at: timestamp("generated_at", { withTimezone: true }),
  created_at: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
});
```

Add `deployments` table after `eval_pairs`:
```typescript
export const deployments = pgTable("deployments", {
  id: uuid("id").primaryKey().$defaultFn(() => crypto.randomUUID()),
  generation_id: uuid("generation_id")
    .notNull()
    .references(() => generations.id, { onDelete: "cascade" }),
  status: varchar("status", { length: 32 }).notNull().default("canary"),
  traffic_split: jsonb("traffic_split").notNull().default({ baseline: 0.9, variant: 0.1 }),
  error_count: integer("error_count").notNull().default(0),
  total_calls: integer("total_calls").notNull().default(0),
  created_at: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  updated_at: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
});
```

Add types at the bottom:
```typescript
export type Deployment = typeof deployments.$inferSelect;
```

- [ ] **Step 2: Add enqueueGenerate to jobs.ts**

In `apps/dashboard/src/lib/db/jobs.ts`, add import and function:

```typescript
import { generations, ... } from "./schema";  // add generations to existing import

export async function enqueueGenerate(opts: {
  userId: string;
  inferenceId: string;
}): Promise<{ generationId: string; jobId: string }> {
  const genRows = await db
    .insert(generations)
    .values({ inference_id: opts.inferenceId, status: "pending" })
    .returning({ id: generations.id });
  const generationId = genRows[0]!.id;

  const jobRows = await db
    .insert(verum_jobs)
    .values({
      kind: "generate",
      payload: { inference_id: opts.inferenceId, generation_id: generationId },
      owner_user_id: opts.userId,
    })
    .returning({ id: verum_jobs.id });

  return { generationId, jobId: jobRows[0]!.id };
}

export async function approveGeneration(userId: string, generationId: string): Promise<boolean> {
  // Verify ownership via inference → analysis → repo → user
  const rows = await db
    .select({ g: generations })
    .from(generations)
    .innerJoin(inferences, eq(generations.inference_id, inferences.id))
    .innerJoin(analyses, eq(inferences.analysis_id, analyses.id))
    .innerJoin(repos, eq(analyses.repo_id, repos.id))
    .where(and(eq(generations.id, generationId), eq(repos.owner_user_id, userId)))
    .limit(1);

  if (!rows[0]) return false;

  await db
    .update(generations)
    .set({ status: "approved" })
    .where(eq(generations.id, generationId));
  return true;
}
```

Also add the missing imports to the top of `jobs.ts`:
```typescript
import { analyses, generations, harvest_sources, inferences, repos, verum_jobs } from "./schema";
import { and, eq } from "drizzle-orm";
```

- [ ] **Step 3: Add getGeneration query to queries.ts**

In `apps/dashboard/src/lib/db/queries.ts`, add:

```typescript
import { generations, prompt_variants, rag_configs, eval_pairs, deployments, ... } from "./schema";
// add to existing imports: Generation, PromptVariant, RagConfig, EvalPair, Deployment

export async function getGeneration(userId: string, generationId: string) {
  const rows = await db
    .select({ g: generations })
    .from(generations)
    .innerJoin(inferences, eq(generations.inference_id, inferences.id))
    .innerJoin(analyses, eq(inferences.analysis_id, analyses.id))
    .innerJoin(repos, eq(analyses.repo_id, repos.id))
    .where(and(eq(generations.id, generationId), eq(repos.owner_user_id, userId)))
    .limit(1);
  return rows[0]?.g ?? null;
}

export async function getGenerationFull(userId: string, generationId: string) {
  const gen = await getGeneration(userId, generationId);
  if (!gen) return null;

  const variants = await db
    .select()
    .from(prompt_variants)
    .where(eq(prompt_variants.generation_id, generationId))
    .orderBy(prompt_variants.created_at);

  const ragRows = await db
    .select()
    .from(rag_configs)
    .where(eq(rag_configs.generation_id, generationId))
    .limit(1);

  const pairs = await db
    .select()
    .from(eval_pairs)
    .where(eq(eval_pairs.generation_id, generationId))
    .limit(5);

  return { gen, variants, rag: ragRows[0] ?? null, pairs };
}

export async function getLatestGeneration(inferenceId: string) {
  const rows = await db
    .select()
    .from(generations)
    .where(eq(generations.inference_id, inferenceId))
    .orderBy(desc(generations.created_at))
    .limit(1);
  return rows[0] ?? null;
}
```

- [ ] **Step 4: Create GENERATE POST route**

Create `apps/dashboard/src/app/api/v1/generate/route.ts`:

```typescript
import { auth } from "@/auth";
import { enqueueGenerate } from "@/lib/db/jobs";
import { getInference } from "@/lib/db/queries";

export async function POST(req: Request) {
  const session = await auth();
  if (!session?.user) return new Response("unauthorized", { status: 401 });
  const uid = String((session.user as Record<string, unknown>).id ?? "");
  if (!uid) return new Response("unauthorized", { status: 401 });

  const body = await req.json() as { inference_id: string };
  if (!body.inference_id) return new Response("inference_id required", { status: 400 });

  const inference = await getInference(uid, body.inference_id);
  if (!inference) return new Response("not found", { status: 404 });

  const { generationId, jobId } = await enqueueGenerate({
    userId: uid,
    inferenceId: body.inference_id,
  });

  return Response.json({ generation_id: generationId, job_id: jobId }, { status: 202 });
}
```

- [ ] **Step 5: Create GENERATE GET route**

Create `apps/dashboard/src/app/api/v1/generate/[id]/route.ts`:

```typescript
import { auth } from "@/auth";
import { getGenerationFull } from "@/lib/db/queries";

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const session = await auth();
  if (!session?.user) return new Response("unauthorized", { status: 401 });
  const uid = String((session.user as Record<string, unknown>).id ?? "");
  if (!uid) return new Response("unauthorized", { status: 401 });

  const { id } = await params;
  const data = await getGenerationFull(uid, id);
  if (!data) return new Response("not found", { status: 404 });

  return Response.json(data, { headers: { "Cache-Control": "no-store" } });
}
```

- [ ] **Step 6: Create GENERATE approve route**

Create `apps/dashboard/src/app/api/v1/generate/[id]/approve/route.ts`:

```typescript
import { auth } from "@/auth";
import { approveGeneration } from "@/lib/db/jobs";

export async function PATCH(
  _req: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const session = await auth();
  if (!session?.user) return new Response("unauthorized", { status: 401 });
  const uid = String((session.user as Record<string, unknown>).id ?? "");
  if (!uid) return new Response("unauthorized", { status: 401 });

  const { id } = await params;
  const ok = await approveGeneration(uid, id);
  if (!ok) return new Response("not found", { status: 404 });

  return Response.json({ status: "approved" });
}
```

- [ ] **Step 7: Create GENERATE dashboard page**

Create `apps/dashboard/src/app/generate/[inference_id]/page.tsx`:

```tsx
import { notFound, redirect } from "next/navigation";
import { auth } from "@/auth";
import { enqueueGenerate, approveGeneration } from "@/lib/db/jobs";
import { getInference, getLatestGeneration, getGenerationFull } from "@/lib/db/queries";

export default async function GeneratePage({
  params,
  searchParams,
}: {
  params: Promise<{ inference_id: string }>;
  searchParams: Promise<{ trigger?: string; approve?: string }>;
}) {
  const session = await auth();
  if (!session?.user) redirect("/login");
  const uid = String((session.user as Record<string, unknown>).id ?? "");
  if (!uid) redirect("/login");

  const { inference_id } = await params;
  const { trigger, approve } = await searchParams;

  const inference = await getInference(uid, inference_id);
  if (!inference) notFound();

  if (trigger === "1") {
    await enqueueGenerate({ userId: uid, inferenceId: inference_id });
    redirect(`/generate/${inference_id}`);
  }

  const latestGen = await getLatestGeneration(inference_id);

  if (approve === "1" && latestGen) {
    await approveGeneration(uid, latestGen.id);
    redirect(`/deploy/${latestGen.id}`);
  }

  const full = latestGen ? await getGenerationFull(uid, latestGen.id) : null;
  const metricProfile = full?.gen?.metric_profile as {
    primary_metrics: string[];
    secondary_metrics: string[];
    profile_name: string;
  } | null;

  return (
    <main style={{ maxWidth: 800, margin: "40px auto", fontFamily: "monospace", padding: "0 16px" }}>
      <h1 style={{ fontSize: 22, margin: "16px 0 4px" }}>GENERATE — Asset Generation</h1>
      <p style={{ color: "#666", fontSize: 13, marginBottom: 24 }}>
        Domain: <strong>{inference.domain ?? "—"}</strong> · Tone: {inference.tone ?? "—"} · Language: {inference.language ?? "—"}
      </p>

      {!latestGen && (
        <form action={`/generate/${inference_id}?trigger=1`} method="GET">
          <button
            type="submit"
            style={{ background: "#000", color: "#fff", border: "none", padding: "10px 20px", cursor: "pointer", fontSize: 14 }}
          >
            생성 시작
          </button>
        </form>
      )}

      {latestGen && (
        <>
          <div style={{ marginBottom: 16, padding: "8px 12px", background: "#f9f9f9", border: "1px solid #ddd", fontSize: 13 }}>
            Status: <strong>{latestGen.status}</strong>
            {latestGen.status === "pending" && (
              <span style={{ marginLeft: 12, color: "#888" }}>
                생성 중… <a href={`/generate/${inference_id}`}>새로고침</a>
              </span>
            )}
          </div>

          {metricProfile && (
            <div style={{ marginBottom: 20 }}>
              <h2 style={{ fontSize: 14, marginBottom: 6 }}>메트릭 프로파일 — {metricProfile.profile_name}</h2>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                {metricProfile.primary_metrics.map((m) => (
                  <span key={m} style={{ background: "#e0f2fe", padding: "2px 8px", fontSize: 12, borderRadius: 4 }}>{m}</span>
                ))}
                {metricProfile.secondary_metrics.map((m) => (
                  <span key={m} style={{ background: "#f3f4f6", padding: "2px 8px", fontSize: 12, borderRadius: 4, color: "#666" }}>{m}</span>
                ))}
              </div>
            </div>
          )}

          {full && full.variants.length > 0 && (
            <div style={{ marginBottom: 24 }}>
              <h2 style={{ fontSize: 15, marginBottom: 8 }}>프롬프트 Variants ({full.variants.length})</h2>
              {full.variants.map((v) => (
                <details key={v.id} style={{ marginBottom: 8, border: "1px solid #ddd", padding: "8px 12px" }}>
                  <summary style={{ cursor: "pointer", fontSize: 13, fontWeight: "bold" }}>{v.variant_type}</summary>
                  <pre style={{ whiteSpace: "pre-wrap", fontSize: 12, marginTop: 8, color: "#333" }}>{v.content}</pre>
                </details>
              ))}
            </div>
          )}

          {full?.rag && (
            <div style={{ marginBottom: 24 }}>
              <h2 style={{ fontSize: 15, marginBottom: 8 }}>RAG Config</h2>
              <table style={{ fontSize: 13, borderCollapse: "collapse" }}>
                {Object.entries(full.rag).filter(([k]) => k !== "id" && k !== "generation_id" && k !== "created_at").map(([k, v]) => (
                  <tr key={k}>
                    <td style={{ padding: "2px 12px 2px 0", color: "#666" }}>{k}</td>
                    <td style={{ padding: "2px 0" }}>{String(v)}</td>
                  </tr>
                ))}
              </table>
            </div>
          )}

          {full && full.pairs.length > 0 && (
            <div style={{ marginBottom: 24 }}>
              <h2 style={{ fontSize: 15, marginBottom: 8 }}>Eval Pairs (처음 5개)</h2>
              {full.pairs.map((p, i) => (
                <div key={p.id} style={{ marginBottom: 8, padding: "8px 12px", background: "#f9f9f9", border: "1px solid #ddd", fontSize: 12 }}>
                  <strong>Q{i + 1}:</strong> {p.query}<br />
                  <span style={{ color: "#555" }}>A: {p.expected_answer}</span>
                </div>
              ))}
            </div>
          )}

          {latestGen.status === "done" && (
            <form action={`/generate/${inference_id}?approve=1`} method="GET">
              <button
                type="submit"
                style={{ background: "#16a34a", color: "#fff", border: "none", padding: "10px 24px", cursor: "pointer", fontSize: 14 }}
              >
                승인 → DEPLOY
              </button>
            </form>
          )}
        </>
      )}
    </main>
  );
}
```

- [ ] **Step 8: Update ROADMAP F-3.5 to ✅**

- [ ] **Step 9: Commit**

```bash
git add apps/dashboard/src/lib/db/schema.ts \
        apps/dashboard/src/lib/db/jobs.ts \
        apps/dashboard/src/lib/db/queries.ts \
        apps/dashboard/src/app/api/v1/generate/ \
        apps/dashboard/src/app/generate/ \
        docs/ROADMAP.md
git commit -m "feat(generate): F-3.5 GENERATE API endpoints and dashboard UI"
```

---

## Task 6: DEPLOY Engine + API (F-3.6 + F-3.7)

**Files:**
- Create: `apps/api/src/loop/deploy/__init__.py`
- Create: `apps/api/src/loop/deploy/models.py`
- Create: `apps/api/src/loop/deploy/engine.py`
- Create: `apps/api/src/loop/deploy/repository.py`
- Create: `apps/api/src/worker/handlers/deploy.py`
- Modify: `apps/api/src/worker/runner.py`
- Create: `apps/api/tests/loop/deploy/__init__.py`
- Create: `apps/api/tests/loop/deploy/test_engine.py`
- Create: `apps/dashboard/src/app/api/v1/deploy/route.ts`
- Create: `apps/dashboard/src/app/api/v1/deploy/[id]/route.ts`
- Create: `apps/dashboard/src/app/api/v1/deploy/[id]/traffic/route.ts`
- Create: `apps/dashboard/src/app/api/v1/deploy/[id]/rollback/route.ts`
- Create: `apps/dashboard/src/app/api/v1/deploy/[id]/config/route.ts`
- Create: `apps/dashboard/src/app/deploy/[id]/page.tsx`

- [ ] **Step 1: Write failing tests**

Create `apps/api/tests/loop/deploy/__init__.py` (empty).

Create `apps/api/tests/loop/deploy/test_engine.py`:

```python
import pytest
from src.loop.deploy.engine import compute_traffic_split, should_auto_rollback


def test_compute_traffic_split_canary():
    split = compute_traffic_split(0.1)
    assert split == {"baseline": 0.9, "variant": 0.1}


def test_compute_traffic_split_full():
    split = compute_traffic_split(1.0)
    assert split == {"baseline": 0.0, "variant": 1.0}


def test_compute_traffic_split_clamps_to_zero_one():
    split = compute_traffic_split(1.5)
    assert split["variant"] == 1.0
    split2 = compute_traffic_split(-0.1)
    assert split2["variant"] == 0.0


def test_no_rollback_insufficient_calls():
    # Less than 100 total calls — never rollback regardless of error rate
    assert not should_auto_rollback(error_count=50, total_calls=50, threshold=5.0)


def test_rollback_triggered_when_error_rate_exceeds_threshold():
    # 100 calls, 10 errors = 10% error rate vs 1% baseline → 10× > 5× → rollback
    assert should_auto_rollback(error_count=10, total_calls=100, threshold=5.0)


def test_no_rollback_error_rate_within_threshold():
    # 100 calls, 3 errors = 3% vs 1% baseline → 3× < 5× → no rollback
    assert not should_auto_rollback(error_count=3, total_calls=100, threshold=5.0)
```

- [ ] **Step 2: Run to verify failure**

```bash
cd apps/api
PYTHONPATH=. pytest tests/loop/deploy/test_engine.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Create deploy models**

Create `apps/api/src/loop/deploy/__init__.py` (empty).

Create `apps/api/src/loop/deploy/models.py`:

```python
"""Pydantic models for the DEPLOY stage ([5] of The Verum Loop)."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DeploymentConfig(BaseModel):
    traffic_split: float = Field(default=0.10, ge=0.0, le=1.0)
    rollback_threshold: float = Field(default=5.0, description="Error rate multiplier vs 1% baseline")


class Deployment(BaseModel):
    deployment_id: UUID
    generation_id: UUID
    status: str  # "canary" | "full" | "rolled_back" | "archived"
    traffic_split: dict[str, float]
    error_count: int
    total_calls: int
    created_at: datetime
    updated_at: datetime


class DeploymentConfigResponse(BaseModel):
    """Lightweight response for SDK polling — no auth required beyond API key."""
    deployment_id: str
    status: str
    traffic_split: float  # fraction to variant, e.g. 0.1
    variant_prompt: str | None
```

- [ ] **Step 4: Create deploy engine**

Create `apps/api/src/loop/deploy/engine.py`:

```python
"""Pure functions for the DEPLOY stage ([5] of The Verum Loop)."""
from __future__ import annotations

_BASELINE_ERROR_RATE = 0.01  # 1% assumed baseline when no prior data


def compute_traffic_split(variant_fraction: float) -> dict[str, float]:
    """Convert a variant fraction (0.0–1.0) to a traffic_split dict."""
    fraction = max(0.0, min(1.0, variant_fraction))
    return {"baseline": round(1.0 - fraction, 10), "variant": fraction}


def should_auto_rollback(
    error_count: int,
    total_calls: int,
    threshold: float = 5.0,
) -> bool:
    """Return True if the error rate exceeds threshold × baseline and calls ≥ 100."""
    if total_calls < 100:
        return False
    error_rate = error_count / total_calls
    return error_rate > _BASELINE_ERROR_RATE * threshold
```

- [ ] **Step 5: Run tests to verify pass**

```bash
cd apps/api
PYTHONPATH=. pytest tests/loop/deploy/test_engine.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 6: Create deploy repository**

Create `apps/api/src/loop/deploy/repository.py`:

```python
"""Database I/O for the DEPLOY stage."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.loop.deploy.engine import compute_traffic_split
from src.loop.deploy.models import Deployment


async def create_deployment(
    db: AsyncSession,
    generation_id: uuid.UUID,
    variant_fraction: float = 0.10,
) -> Deployment:
    split = compute_traffic_split(variant_fraction)
    row = (await db.execute(
        text(
            "INSERT INTO deployments (generation_id, status, traffic_split)"
            " VALUES (:gid, 'canary', :split::jsonb)"
            " RETURNING id, generation_id, status, traffic_split, error_count, total_calls, created_at, updated_at"
        ),
        {"gid": str(generation_id), "split": json.dumps(split)},
    )).mappings().first()
    await db.commit()
    assert row is not None
    return _row_to_deployment(dict(row))


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
            "UPDATE deployments SET traffic_split = :split::jsonb, updated_at = now()"
            " WHERE id = :id"
            " RETURNING *"
        ),
        {"split": json.dumps(split), "id": str(deployment_id)},
    )).mappings().first()
    await db.commit()
    return _row_to_deployment(dict(row)) if row else None


async def rollback_deployment(db: AsyncSession, deployment_id: uuid.UUID) -> Deployment | None:
    split = json.dumps({"baseline": 1.0, "variant": 0.0})
    row = (await db.execute(
        text(
            "UPDATE deployments SET status = 'rolled_back', traffic_split = :split::jsonb, updated_at = now()"
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


def _row_to_deployment(row: dict) -> Deployment:
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
```

- [ ] **Step 7: Create worker handler**

Create `apps/api/src/worker/handlers/deploy.py`:

```python
"""DEPLOY job handler.

Payload schema:
  generation_id: str (UUID)
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.loop.deploy.repository import create_deployment

logger = logging.getLogger(__name__)


async def handle_deploy(
    db: AsyncSession,
    owner_user_id: uuid.UUID,
    payload: dict[str, Any],
) -> dict[str, Any]:
    generation_id = uuid.UUID(payload["generation_id"])
    deployment = await create_deployment(db, generation_id, variant_fraction=0.10)
    logger.info("DEPLOY complete: deployment_id=%s status=%s", deployment.deployment_id, deployment.status)
    return {
        "deployment_id": str(deployment.deployment_id),
        "status": deployment.status,
        "traffic_split": deployment.traffic_split,
    }
```

- [ ] **Step 8: Register deploy handler in runner.py**

In `apps/api/src/worker/runner.py`, add import and register:

```python
from .handlers.deploy import handle_deploy  # add to existing imports

_HANDLERS = {
    "analyze": handle_analyze,
    "infer": handle_infer,
    "harvest": handle_harvest,
    "retrieve": handle_retrieve,
    "generate": handle_generate,
    "deploy": handle_deploy,   # add this line
}
```

- [ ] **Step 9: Add enqueueDeployment to jobs.ts**

In `apps/dashboard/src/lib/db/jobs.ts`, add:

```typescript
import { deployments, ... } from "./schema";  // add deployments to import

export async function enqueueDeployment(opts: {
  userId: string;
  generationId: string;
}): Promise<string> {
  const rows = await db
    .insert(verum_jobs)
    .values({
      kind: "deploy",
      payload: { generation_id: opts.generationId },
      owner_user_id: opts.userId,
    })
    .returning({ id: verum_jobs.id });
  return rows[0]!.id;
}

export async function updateDeploymentTraffic(deploymentId: string, split: number) {
  await db
    .update(deployments)
    .set({ traffic_split: { baseline: 1 - split, variant: split }, updated_at: new Date() })
    .where(eq(deployments.id, deploymentId));
}

export async function rollbackDeployment(deploymentId: string) {
  await db
    .update(deployments)
    .set({ status: "rolled_back", traffic_split: { baseline: 1.0, variant: 0.0 }, updated_at: new Date() })
    .where(eq(deployments.id, deploymentId));
}
```

- [ ] **Step 10: Add getDeployment queries**

In `apps/dashboard/src/lib/db/queries.ts`, add:

```typescript
export async function getDeployment(userId: string, deploymentId: string) {
  const rows = await db
    .select({ d: deployments })
    .from(deployments)
    .innerJoin(generations, eq(deployments.generation_id, generations.id))
    .innerJoin(inferences, eq(generations.inference_id, inferences.id))
    .innerJoin(analyses, eq(inferences.analysis_id, analyses.id))
    .innerJoin(repos, eq(analyses.repo_id, repos.id))
    .where(and(eq(deployments.id, deploymentId), eq(repos.owner_user_id, userId)))
    .limit(1);
  return rows[0]?.d ?? null;
}

export async function getDeploymentByGenerationId(generationId: string) {
  const rows = await db
    .select()
    .from(deployments)
    .where(eq(deployments.generation_id, generationId))
    .orderBy(desc(deployments.created_at))
    .limit(1);
  return rows[0] ?? null;
}

export async function getVariantPrompt(deploymentId: string): Promise<string | null> {
  const rows = await db.execute(
    sql`SELECT pv.content FROM deployments d
        JOIN generations g ON g.id = d.generation_id
        JOIN prompt_variants pv ON pv.generation_id = g.id
        WHERE d.id = ${deploymentId}::uuid AND pv.variant_type = 'cot'
        LIMIT 1`,
  );
  const row = rows.rows[0] as { content: string } | undefined;
  return row?.content ?? null;
}
```

- [ ] **Step 11: Create DEPLOY POST route**

Create `apps/dashboard/src/app/api/v1/deploy/route.ts`:

```typescript
import { auth } from "@/auth";
import { enqueueDeployment } from "@/lib/db/jobs";
import { getGeneration } from "@/lib/db/queries";

export async function POST(req: Request) {
  const session = await auth();
  if (!session?.user) return new Response("unauthorized", { status: 401 });
  const uid = String((session.user as Record<string, unknown>).id ?? "");
  if (!uid) return new Response("unauthorized", { status: 401 });

  const body = await req.json() as { generation_id: string };
  if (!body.generation_id) return new Response("generation_id required", { status: 400 });

  const gen = await getGeneration(uid, body.generation_id);
  if (!gen) return new Response("not found", { status: 404 });
  if (gen.status !== "approved") return new Response("generation not approved", { status: 409 });

  const jobId = await enqueueDeployment({ userId: uid, generationId: body.generation_id });
  return Response.json({ job_id: jobId }, { status: 202 });
}
```

- [ ] **Step 12: Create DEPLOY GET route**

Create `apps/dashboard/src/app/api/v1/deploy/[id]/route.ts`:

```typescript
import { auth } from "@/auth";
import { getDeployment } from "@/lib/db/queries";

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const session = await auth();
  if (!session?.user) return new Response("unauthorized", { status: 401 });
  const uid = String((session.user as Record<string, unknown>).id ?? "");
  if (!uid) return new Response("unauthorized", { status: 401 });

  const { id } = await params;
  const deployment = await getDeployment(uid, id);
  if (!deployment) return new Response("not found", { status: 404 });

  return Response.json(deployment, { headers: { "Cache-Control": "no-store" } });
}
```

- [ ] **Step 13: Create DEPLOY traffic PATCH route**

Create `apps/dashboard/src/app/api/v1/deploy/[id]/traffic/route.ts`:

```typescript
import { auth } from "@/auth";
import { updateDeploymentTraffic } from "@/lib/db/jobs";
import { getDeployment } from "@/lib/db/queries";

export async function PATCH(
  req: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const session = await auth();
  if (!session?.user) return new Response("unauthorized", { status: 401 });
  const uid = String((session.user as Record<string, unknown>).id ?? "");
  if (!uid) return new Response("unauthorized", { status: 401 });

  const { id } = await params;
  const deployment = await getDeployment(uid, id);
  if (!deployment) return new Response("not found", { status: 404 });

  const body = await req.json() as { split: number };
  if (typeof body.split !== "number" || body.split < 0 || body.split > 1) {
    return new Response("split must be a number between 0 and 1", { status: 400 });
  }

  await updateDeploymentTraffic(id, body.split);
  return Response.json({ ok: true });
}
```

- [ ] **Step 14: Create DEPLOY rollback route**

Create `apps/dashboard/src/app/api/v1/deploy/[id]/rollback/route.ts`:

```typescript
import { auth } from "@/auth";
import { rollbackDeployment } from "@/lib/db/jobs";
import { getDeployment } from "@/lib/db/queries";

export async function POST(
  _req: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const session = await auth();
  if (!session?.user) return new Response("unauthorized", { status: 401 });
  const uid = String((session.user as Record<string, unknown>).id ?? "");
  if (!uid) return new Response("unauthorized", { status: 401 });

  const { id } = await params;
  const deployment = await getDeployment(uid, id);
  if (!deployment) return new Response("not found", { status: 404 });

  await rollbackDeployment(id);
  return Response.json({ status: "rolled_back" });
}
```

- [ ] **Step 15: Create SDK config endpoint (API key auth)**

Create `apps/dashboard/src/app/api/v1/deploy/[id]/config/route.ts`:

```typescript
import { getDeploymentByGenerationId, getVariantPrompt } from "@/lib/db/queries";
import { db } from "@/lib/db/client";
import { deployments } from "@/lib/db/schema";
import { eq } from "drizzle-orm";

export async function GET(
  req: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  // API key auth — no session required (SDK calls this)
  const apiKey = req.headers.get("x-verum-api-key") ?? req.headers.get("authorization")?.replace("Bearer ", "");
  if (!apiKey || apiKey !== process.env.VERUM_API_KEY) {
    return new Response("unauthorized", { status: 401 });
  }

  const { id } = await params;
  const rows = await db
    .select()
    .from(deployments)
    .where(eq(deployments.id, id))
    .limit(1);
  const deployment = rows[0];
  if (!deployment) return new Response("not found", { status: 404 });

  const split = deployment.traffic_split as { baseline: number; variant: number };
  const variantPrompt = await getVariantPrompt(id);

  return Response.json({
    deployment_id: id,
    status: deployment.status,
    traffic_split: split.variant,
    variant_prompt: variantPrompt,
  }, { headers: { "Cache-Control": "no-store" } });
}
```

- [ ] **Step 16: Create DEPLOY dashboard page**

Create `apps/dashboard/src/app/deploy/[id]/page.tsx`:

```tsx
import { notFound, redirect } from "next/navigation";
import { auth } from "@/auth";
import { enqueueDeployment, rollbackDeployment } from "@/lib/db/jobs";
import { getGeneration, getDeployment, getDeploymentByGenerationId } from "@/lib/db/queries";

export default async function DeployPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ rollback?: string; promote?: string; generation_id?: string }>;
}) {
  const session = await auth();
  if (!session?.user) redirect("/login");
  const uid = String((session.user as Record<string, unknown>).id ?? "");
  if (!uid) redirect("/login");

  const { id } = await params;
  const { rollback, promote, generation_id } = await searchParams;

  // If generation_id provided, look up or create deployment
  if (generation_id) {
    const existing = await getDeploymentByGenerationId(generation_id);
    if (!existing) {
      await enqueueDeployment({ userId: uid, generationId: generation_id });
    }
    redirect(`/deploy/${existing?.id ?? id}`);
  }

  if (rollback === "1") {
    await rollbackDeployment(id);
    redirect(`/deploy/${id}`);
  }

  const deployment = await getDeployment(uid, id);
  if (!deployment) notFound();

  const split = deployment.traffic_split as { baseline: number; variant: number };
  const variantPct = Math.round((split.variant ?? 0) * 100);
  const errorRate = deployment.total_calls > 0
    ? ((deployment.error_count / deployment.total_calls) * 100).toFixed(2)
    : "0.00";

  return (
    <main style={{ maxWidth: 720, margin: "40px auto", fontFamily: "monospace", padding: "0 16px" }}>
      <h1 style={{ fontSize: 22, margin: "16px 0 4px" }}>DEPLOY — Canary Deployment</h1>

      <div style={{ display: "flex", gap: 32, marginBottom: 24, marginTop: 16 }}>
        <div><strong>Status</strong><br />{deployment.status}</div>
        <div><strong>Variant traffic</strong><br />{variantPct}%</div>
        <div><strong>Total calls</strong><br />{deployment.total_calls}</div>
        <div><strong>Error rate</strong><br />{errorRate}%</div>
      </div>

      {deployment.status === "rolled_back" && (
        <div style={{ background: "#fef2f2", border: "1px solid #ef4444", padding: "12px 16px", marginBottom: 16 }}>
          <strong style={{ color: "#ef4444" }}>롤백됨</strong> — 기본 프롬프트로 복원되었습니다.
        </div>
      )}

      <div style={{ marginBottom: 24 }}>
        <h2 style={{ fontSize: 14, marginBottom: 8 }}>트래픽 조정</h2>
        <div style={{ display: "flex", gap: 8 }}>
          {[10, 50, 100].map((pct) => (
            <form key={pct} action={`/api/v1/deploy/${id}/traffic`} method="POST">
              <input type="hidden" name="split" value={pct / 100} />
              <button
                type="submit"
                style={{
                  padding: "6px 16px",
                  border: "1px solid #ddd",
                  background: variantPct === pct ? "#000" : "#fff",
                  color: variantPct === pct ? "#fff" : "#000",
                  cursor: "pointer",
                  fontSize: 13,
                }}
              >
                {pct}%
              </button>
            </form>
          ))}
        </div>
      </div>

      {deployment.status !== "rolled_back" && (
        <form action={`/deploy/${id}?rollback=1`} method="GET">
          <button
            type="submit"
            style={{ background: "#ef4444", color: "#fff", border: "none", padding: "8px 18px", cursor: "pointer", fontSize: 13 }}
          >
            롤백
          </button>
        </form>
      )}
    </main>
  );
}
```

- [ ] **Step 17: Run deploy tests**

```bash
cd apps/api
PYTHONPATH=. pytest tests/loop/deploy/ -v
```

Expected: all 6 tests PASS.

- [ ] **Step 18: Update ROADMAP F-3.6 and F-3.7 to ✅**

- [ ] **Step 19: Commit**

```bash
git add apps/api/src/loop/deploy/ \
        apps/api/src/worker/handlers/deploy.py \
        apps/api/src/worker/runner.py \
        apps/api/tests/loop/deploy/ \
        apps/dashboard/src/app/api/v1/deploy/ \
        apps/dashboard/src/app/deploy/ \
        apps/dashboard/src/lib/db/jobs.ts \
        apps/dashboard/src/lib/db/queries.ts \
        docs/ROADMAP.md
git commit -m "feat(deploy): F-3.6 F-3.7 DEPLOY engine, API endpoints, and dashboard UI"
```

---

## Task 7: Python SDK (F-3.8)

**Files:**
- Create: `packages/sdk-python/src/verum/client.py`
- Create: `packages/sdk-python/src/verum/_cache.py`
- Create: `packages/sdk-python/src/verum/_router.py`
- Modify: `packages/sdk-python/src/verum/__init__.py`
- Create: `packages/sdk-python/tests/__init__.py`
- Create: `packages/sdk-python/tests/test_client.py`

- [ ] **Step 1: Write failing tests**

Create `packages/sdk-python/tests/__init__.py` (empty).

Create `packages/sdk-python/tests/test_client.py`:

```python
import asyncio
import json
import os
import time
import pytest
import respx
import httpx
from verum import Client
from verum._cache import DeploymentConfigCache
from verum._router import choose_variant


# ── Cache tests ────────────────────────────────────────────────────────────────

def test_cache_miss_returns_none():
    cache = DeploymentConfigCache(ttl=60)
    assert cache.get("dep-1") is None


def test_cache_set_and_hit():
    cache = DeploymentConfigCache(ttl=60)
    config = {"traffic_split": 0.1, "variant_prompt": "CoT prompt", "status": "canary"}
    cache.set("dep-1", config)
    result = cache.get("dep-1")
    assert result == config


def test_cache_expires():
    cache = DeploymentConfigCache(ttl=0)  # instant expiry
    cache.set("dep-1", {"traffic_split": 0.1, "variant_prompt": "x", "status": "canary"})
    time.sleep(0.01)
    assert cache.get("dep-1") is None


# ── Router tests ────────────────────────────────────────────────────────────────

def test_choose_variant_always_baseline_at_zero():
    for _ in range(100):
        assert choose_variant(0.0) == "baseline"


def test_choose_variant_always_variant_at_one():
    for _ in range(100):
        assert choose_variant(1.0) == "variant"


def test_choose_variant_statistically_correct():
    results = [choose_variant(0.5) for _ in range(1000)]
    variant_count = results.count("variant")
    # Should be roughly 50% ± 10%
    assert 400 < variant_count < 600


# ── Client integration tests ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_chat_without_deployment_id_passes_through():
    client = Client(api_url="http://verum-test.local", api_key="test-key")

    # No deployment_id — should just return messages unchanged
    result = await client.chat(
        messages=[{"role": "user", "content": "Hello"}],
        provider="openai",
        model="gpt-4",
        deployment_id=None,
    )
    # Without a real LLM, we verify it returns the messages (passthrough mode returns input)
    assert result["messages"][0]["content"] == "Hello"


@pytest.mark.asyncio
async def test_retrieve_calls_api():
    with respx.mock(base_url="http://verum-test.local") as mock:
        mock.post("/api/v1/retrieve-sdk").mock(
            return_value=httpx.Response(200, json={"chunks": [{"content": "Tarot info"}]})
        )
        client = Client(api_url="http://verum-test.local", api_key="test-key")
        chunks = await client.retrieve(query="what is the Moon card?", collection_name="arcana-tarot-knowledge")
        assert len(chunks) == 1
        assert chunks[0]["content"] == "Tarot info"


@pytest.mark.asyncio
async def test_feedback_calls_api():
    with respx.mock(base_url="http://verum-test.local") as mock:
        mock.post("/api/v1/feedback").mock(return_value=httpx.Response(204))
        client = Client(api_url="http://verum-test.local", api_key="test-key")
        await client.feedback(trace_id="trace-123", score=1)
        assert mock.calls.called
```

- [ ] **Step 2: Run to verify failure**

```bash
cd packages/sdk-python
pip install -e ".[dev]" 2>/dev/null || pip install -e "."
pip install respx pytest pytest-asyncio
PYTHONPATH=src pytest tests/test_client.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'verum.client'`

- [ ] **Step 3: Implement _cache.py**

Create `packages/sdk-python/src/verum/_cache.py`:

```python
"""In-memory TTL cache for deployment configs (60 second default TTL)."""
from __future__ import annotations

import time
from typing import Any


class DeploymentConfigCache:
    def __init__(self, ttl: float = 60.0) -> None:
        self._ttl = ttl
        self._store: dict[str, tuple[Any, float]] = {}

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.monotonic() > expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (value, time.monotonic() + self._ttl)
```

- [ ] **Step 4: Implement _router.py**

Create `packages/sdk-python/src/verum/_router.py`:

```python
"""Traffic split routing logic for the Verum SDK."""
from __future__ import annotations

import random


def choose_variant(split: float) -> str:
    """Return 'variant' or 'baseline' based on the given split fraction.

    Args:
        split: Fraction of traffic to route to the variant (0.0 to 1.0).

    Returns:
        'variant' if this call should use the variant prompt, 'baseline' otherwise.
    """
    return "variant" if random.random() < split else "baseline"
```

- [ ] **Step 5: Implement client.py**

Create `packages/sdk-python/src/verum/client.py`:

```python
"""Verum SDK client — wraps LLM calls with deployment routing."""
from __future__ import annotations

import os
from typing import Any

import httpx

from verum._cache import DeploymentConfigCache
from verum._router import choose_variant

_DEFAULT_CACHE_TTL = 60.0


class Client:
    """Connect an AI service to The Verum Loop.

    Usage:
        client = verum.Client()  # reads VERUM_API_URL / VERUM_API_KEY from env
        chunks = await client.retrieve(query="...", collection_name="arcana-tarot-knowledge")
        response = await client.chat(messages=[...], deployment_id="...", provider="grok", model="grok-2-1212")
    """

    def __init__(
        self,
        api_url: str | None = None,
        api_key: str | None = None,
        cache_ttl: float = _DEFAULT_CACHE_TTL,
    ) -> None:
        self._api_url = (api_url or os.environ.get("VERUM_API_URL", "")).rstrip("/")
        self._api_key = api_key or os.environ.get("VERUM_API_KEY", "")
        self._cache: DeploymentConfigCache = DeploymentConfigCache(ttl=cache_ttl)

    # ── Public API ────────────────────────────────────────────────────────────

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        deployment_id: str | None = None,
        provider: str = "openai",
        model: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Call the LLM with optional Verum routing.

        If deployment_id is given, fetches the current traffic split and may
        replace the system prompt with the variant. Actual LLM call is made
        directly by the caller — this returns the (possibly modified) messages.

        For Phase 3 (no proxy), this returns {"messages": ..., "routed_to": ...}.
        In Phase 4, telemetry will be added here.
        """
        if not deployment_id:
            return {"messages": messages, "routed_to": "baseline", "deployment_id": None}

        config = await self._get_deployment_config(deployment_id)
        routed_to = choose_variant(config.get("traffic_split", 0.0))

        if routed_to == "variant" and config.get("variant_prompt"):
            messages = list(messages)
            if messages and messages[0].get("role") == "system":
                messages[0] = {**messages[0], "content": config["variant_prompt"]}
            else:
                messages = [{"role": "system", "content": config["variant_prompt"]}, *messages]

        return {"messages": messages, "routed_to": routed_to, "deployment_id": deployment_id}

    async def retrieve(
        self,
        query: str,
        *,
        collection_name: str,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Retrieve knowledge chunks from the Verum RAG index."""
        async with httpx.AsyncClient() as http:
            resp = await http.post(
                f"{self._api_url}/api/v1/retrieve-sdk",
                json={"query": query, "collection_name": collection_name, "top_k": top_k},
                headers=self._headers(),
                timeout=10.0,
            )
            resp.raise_for_status()
            return resp.json().get("chunks", [])

    async def feedback(self, trace_id: str, score: int) -> None:
        """Record user feedback for a trace. score: 1 (positive) or -1 (negative)."""
        async with httpx.AsyncClient() as http:
            resp = await http.post(
                f"{self._api_url}/api/v1/feedback",
                json={"trace_id": trace_id, "score": score},
                headers=self._headers(),
                timeout=5.0,
            )
            resp.raise_for_status()

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _get_deployment_config(self, deployment_id: str) -> dict[str, Any]:
        cached = self._cache.get(deployment_id)
        if cached is not None:
            return cached  # type: ignore[return-value]

        async with httpx.AsyncClient() as http:
            resp = await http.get(
                f"{self._api_url}/api/v1/deploy/{deployment_id}/config",
                headers=self._headers(),
                timeout=5.0,
            )
            resp.raise_for_status()
            config: dict[str, Any] = resp.json()

        self._cache.set(deployment_id, config)
        return config

    def _headers(self) -> dict[str, str]:
        return {"x-verum-api-key": self._api_key}
```

- [ ] **Step 6: Update __init__.py**

Replace `packages/sdk-python/src/verum/__init__.py`:

```python
"""Verum SDK — connect your AI service to The Verum Loop."""
from verum.client import Client

__version__ = "0.1.0"
__all__ = ["Client"]
```

- [ ] **Step 7: Add pytest-asyncio config to pyproject.toml**

In `packages/sdk-python/pyproject.toml`, add:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8",
    "pytest-asyncio>=0.23",
    "respx>=0.21",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

- [ ] **Step 8: Run tests**

```bash
cd packages/sdk-python
pip install -e ".[dev]"
pip install respx
PYTHONPATH=src pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 9: Update ROADMAP F-3.8 to ✅**

- [ ] **Step 10: Commit**

```bash
git add packages/sdk-python/
git commit -m "feat(sdk-python): F-3.8 verum.Client with chat, retrieve, feedback"
```

---

## Task 8: TypeScript SDK (F-3.9)

**Files:**
- Create: `packages/sdk-typescript/src/cache.ts`
- Create: `packages/sdk-typescript/src/router.ts`
- Create: `packages/sdk-typescript/src/client.ts`
- Modify: `packages/sdk-typescript/src/index.ts`
- Create: `packages/sdk-typescript/tests/client.test.ts`

- [ ] **Step 1: Check existing SDK structure**

```bash
ls packages/sdk-typescript/src/
cat packages/sdk-typescript/package.json
```

Note the existing file structure before creating new files.

- [ ] **Step 2: Create cache.ts**

Create `packages/sdk-typescript/src/cache.ts`:

```typescript
interface CacheEntry<T> {
  value: T;
  expiresAt: number;
}

export class DeploymentConfigCache<T = unknown> {
  private store = new Map<string, CacheEntry<T>>();

  constructor(private readonly ttlMs: number = 60_000) {}

  get(key: string): T | undefined {
    const entry = this.store.get(key);
    if (!entry) return undefined;
    if (Date.now() > entry.expiresAt) {
      this.store.delete(key);
      return undefined;
    }
    return entry.value;
  }

  set(key: string, value: T): void {
    this.store.set(key, { value, expiresAt: Date.now() + this.ttlMs });
  }
}
```

- [ ] **Step 3: Create router.ts**

Create `packages/sdk-typescript/src/router.ts`:

```typescript
export function chooseVariant(split: number): "variant" | "baseline" {
  return Math.random() < split ? "variant" : "baseline";
}
```

- [ ] **Step 4: Create client.ts**

Create `packages/sdk-typescript/src/client.ts`:

```typescript
import { DeploymentConfigCache } from "./cache";
import { chooseVariant } from "./router";

export interface ChatMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

interface DeploymentConfig {
  deployment_id: string;
  status: string;
  traffic_split: number;
  variant_prompt: string | null;
}

interface ChatParams {
  messages: ChatMessage[];
  deploymentId?: string;
  provider?: "openai" | "anthropic" | "grok";
  model: string;
  [key: string]: unknown;
}

interface ChatResult {
  messages: ChatMessage[];
  routed_to: "variant" | "baseline";
  deployment_id: string | null;
}

interface RetrieveParams {
  query: string;
  collectionName: string;
  topK?: number;
}

interface Chunk {
  content: string;
  [key: string]: unknown;
}

interface FeedbackParams {
  traceId: string;
  score: 1 | -1;
}

export class VerumClient {
  private readonly apiUrl: string;
  private readonly apiKey: string;
  private readonly cache: DeploymentConfigCache<DeploymentConfig>;

  constructor(options?: { apiUrl?: string; apiKey?: string; cacheTtlMs?: number }) {
    this.apiUrl = (options?.apiUrl ?? process.env["VERUM_API_URL"] ?? "").replace(/\/$/, "");
    this.apiKey = options?.apiKey ?? process.env["VERUM_API_KEY"] ?? "";
    this.cache = new DeploymentConfigCache(options?.cacheTtlMs ?? 60_000);
  }

  async chat(params: ChatParams): Promise<ChatResult> {
    const { messages, deploymentId } = params;

    if (!deploymentId) {
      return { messages, routed_to: "baseline", deployment_id: null };
    }

    const config = await this.getDeploymentConfig(deploymentId);
    const routedTo = chooseVariant(config.traffic_split);
    let finalMessages = [...messages];

    if (routedTo === "variant" && config.variant_prompt) {
      if (finalMessages[0]?.role === "system") {
        finalMessages[0] = { ...finalMessages[0], content: config.variant_prompt };
      } else {
        finalMessages = [{ role: "system", content: config.variant_prompt }, ...finalMessages];
      }
    }

    return { messages: finalMessages, routed_to: routedTo, deployment_id: deploymentId };
  }

  async retrieve(params: RetrieveParams): Promise<Chunk[]> {
    const res = await fetch(`${this.apiUrl}/api/v1/retrieve-sdk`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-verum-api-key": this.apiKey },
      body: JSON.stringify({
        query: params.query,
        collection_name: params.collectionName,
        top_k: params.topK ?? 5,
      }),
    });
    if (!res.ok) throw new Error(`retrieve failed: ${res.status}`);
    const data = await res.json() as { chunks: Chunk[] };
    return data.chunks;
  }

  async feedback(params: FeedbackParams): Promise<void> {
    const res = await fetch(`${this.apiUrl}/api/v1/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-verum-api-key": this.apiKey },
      body: JSON.stringify({ trace_id: params.traceId, score: params.score }),
    });
    if (!res.ok) throw new Error(`feedback failed: ${res.status}`);
  }

  private async getDeploymentConfig(deploymentId: string): Promise<DeploymentConfig> {
    const cached = this.cache.get(deploymentId);
    if (cached) return cached;

    const res = await fetch(`${this.apiUrl}/api/v1/deploy/${deploymentId}/config`, {
      headers: { "x-verum-api-key": this.apiKey },
    });
    if (!res.ok) throw new Error(`config fetch failed: ${res.status}`);
    const config = await res.json() as DeploymentConfig;
    this.cache.set(deploymentId, config);
    return config;
  }
}
```

- [ ] **Step 5: Update index.ts**

Replace `packages/sdk-typescript/src/index.ts`:

```typescript
export { VerumClient } from "./client";
export type { ChatMessage } from "./client";
```

- [ ] **Step 6: Write Jest tests**

Create `packages/sdk-typescript/tests/client.test.ts`:

```typescript
import { DeploymentConfigCache } from "../src/cache";
import { chooseVariant } from "../src/router";
import { VerumClient } from "../src/client";

// ── Cache tests ─────────────────────────────────────────────────────────────

describe("DeploymentConfigCache", () => {
  it("returns undefined for a cache miss", () => {
    const cache = new DeploymentConfigCache();
    expect(cache.get("dep-1")).toBeUndefined();
  });

  it("returns cached value before TTL", () => {
    const cache = new DeploymentConfigCache(60_000);
    cache.set("dep-1", { traffic_split: 0.1 } as never);
    expect(cache.get("dep-1")).toEqual({ traffic_split: 0.1 });
  });

  it("returns undefined after TTL expires", async () => {
    const cache = new DeploymentConfigCache(1); // 1ms TTL
    cache.set("dep-1", { traffic_split: 0.1 } as never);
    await new Promise((r) => setTimeout(r, 5));
    expect(cache.get("dep-1")).toBeUndefined();
  });
});

// ── Router tests ─────────────────────────────────────────────────────────────

describe("chooseVariant", () => {
  it("always returns baseline at 0", () => {
    for (let i = 0; i < 100; i++) expect(chooseVariant(0)).toBe("baseline");
  });

  it("always returns variant at 1", () => {
    for (let i = 0; i < 100; i++) expect(chooseVariant(1)).toBe("variant");
  });

  it("distributes roughly 50/50 at 0.5", () => {
    const results = Array.from({ length: 1000 }, () => chooseVariant(0.5));
    const variantCount = results.filter((r) => r === "variant").length;
    expect(variantCount).toBeGreaterThan(400);
    expect(variantCount).toBeLessThan(600);
  });
});

// ── Client tests ─────────────────────────────────────────────────────────────

describe("VerumClient.chat", () => {
  it("passes through when no deploymentId", async () => {
    const client = new VerumClient({ apiUrl: "http://test.local", apiKey: "key" });
    const messages = [{ role: "user" as const, content: "Hello" }];
    const result = await client.chat({ messages, model: "gpt-4" });
    expect(result.routed_to).toBe("baseline");
    expect(result.deployment_id).toBeNull();
    expect(result.messages[0].content).toBe("Hello");
  });

  it("replaces system prompt with variant when routed to variant", async () => {
    const client = new VerumClient({ apiUrl: "http://test.local", apiKey: "key" });
    // Inject a mock config into the cache
    (client as unknown as { cache: DeploymentConfigCache<unknown> }).cache.set("dep-1", {
      deployment_id: "dep-1",
      status: "canary",
      traffic_split: 1.0,  // 100% to variant — always triggers
      variant_prompt: "CoT variant prompt",
    });

    const messages = [
      { role: "system" as const, content: "Original system prompt" },
      { role: "user" as const, content: "User question" },
    ];
    const result = await client.chat({ messages, deploymentId: "dep-1", model: "grok-2-1212" });
    expect(result.routed_to).toBe("variant");
    expect(result.messages[0].content).toBe("CoT variant prompt");
    expect(result.messages[1].content).toBe("User question");
  });
});
```

- [ ] **Step 7: Configure Jest in package.json**

Check if `packages/sdk-typescript/package.json` has Jest config. If not, add:

```json
{
  "scripts": {
    "test": "jest"
  },
  "devDependencies": {
    "@types/jest": "^29",
    "jest": "^29",
    "ts-jest": "^29",
    "typescript": "^5"
  },
  "jest": {
    "preset": "ts-jest",
    "testEnvironment": "node",
    "roots": ["<rootDir>/tests"]
  }
}
```

- [ ] **Step 8: Run tests**

```bash
cd packages/sdk-typescript
npm install
npm test
```

Expected: all 9 tests PASS.

- [ ] **Step 9: TypeScript type check**

```bash
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 10: Update ROADMAP F-3.9 to ✅**

- [ ] **Step 11: Commit**

```bash
git add packages/sdk-typescript/
git commit -m "feat(sdk-typescript): F-3.9 VerumClient with chat, retrieve, feedback"
```

---

## Task 9: ArcanaInsight Integration (F-3.10)

**Files:**
- Create: `examples/arcana-integration/README.md`
- Create: `examples/arcana-integration/before.py`
- Create: `examples/arcana-integration/after.py`
- Create: `examples/arcana-integration/.env.example`

- [ ] **Step 1: Create .env.example**

Create `examples/arcana-integration/.env.example`:

```
# Verum API connection
VERUM_API_URL=https://your-verum-deployment.up.railway.app
VERUM_API_KEY=your-verum-api-key-here

# The deployment ID from the Verum dashboard after approving a generation
VERUM_DEPLOYMENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

- [ ] **Step 2: Create before.py**

Create `examples/arcana-integration/before.py`:

```python
"""ArcanaInsight tarot reading endpoint — BEFORE Verum integration.

This shows the original pattern. The Grok SDK is called directly with
a hardcoded system prompt. No RAG, no A/B testing, no observability.
"""
import os
from openai import AsyncOpenAI  # xai_grok uses OpenAI-compatible client

SYSTEM_PROMPT = """당신은 신비로운 타로 카드 리더입니다. 
카드의 상징과 의미를 깊이 있게 해석하여 질문자에게 통찰을 제공하세요."""

client = AsyncOpenAI(
    api_key=os.environ["XAI_API_KEY"],
    base_url="https://api.x.ai/v1",
)


async def tarot_reading(user_message: str) -> str:
    response = await client.chat.completions.create(
        model="grok-2-1212",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.9,
    )
    return response.choices[0].message.content
```

- [ ] **Step 3: Create after.py**

Create `examples/arcana-integration/after.py`:

```python
"""ArcanaInsight tarot reading endpoint — AFTER Verum integration.

Changes from before.py:
1. verum.retrieve() fetches relevant tarot knowledge before the LLM call.
2. verum.chat() routes 10% of traffic to the Verum-generated CoT variant prompt.
3. No other changes — same Grok model, same response format.

Setup:
  pip install verum
  export VERUM_API_URL=https://your-verum.up.railway.app
  export VERUM_API_KEY=your-api-key
  export VERUM_DEPLOYMENT_ID=your-deployment-id
  export XAI_API_KEY=your-xai-key
"""
import os
from openai import AsyncOpenAI
import verum

SYSTEM_PROMPT = """당신은 신비로운 타로 카드 리더입니다. 
카드의 상징과 의미를 깊이 있게 해석하여 질문자에게 통찰을 제공하세요."""

xai_client = AsyncOpenAI(
    api_key=os.environ["XAI_API_KEY"],
    base_url="https://api.x.ai/v1",
)

verum_client = verum.Client()
DEPLOYMENT_ID = os.environ.get("VERUM_DEPLOYMENT_ID")


async def tarot_reading(user_message: str) -> str:
    # Step 1: retrieve relevant tarot knowledge from Verum's RAG index
    chunks = await verum_client.retrieve(
        query=user_message,
        collection_name="arcana-tarot-knowledge",
        top_k=5,
    )
    context = "\n---\n".join(c["content"] for c in chunks) if chunks else ""

    # Step 2: build messages with RAG context injected
    user_content = f"참고 지식:\n{context}\n\n질문: {user_message}" if context else user_message
    base_messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    # Step 3: route via Verum (10% → CoT variant, 90% → original)
    routed = await verum_client.chat(
        messages=base_messages,
        deployment_id=DEPLOYMENT_ID,
        provider="grok",
        model="grok-2-1212",
    )

    # Step 4: call the actual LLM with the (possibly modified) messages
    response = await xai_client.chat.completions.create(
        model="grok-2-1212",
        messages=routed["messages"],
        temperature=0.9,
    )
    return response.choices[0].message.content
```

- [ ] **Step 4: Create README.md**

Create `examples/arcana-integration/README.md`:

```markdown
# ArcanaInsight × Verum — 통합 가이드

Phase 3 완료 게이트: ArcanaInsight의 타로 상담이 Verum이 생성한 프롬프트와 RAG로 작동.

## 사전 요건

1. Verum 대시보드에서 ArcanaInsight Repo의 GENERATE 단계를 완료하고 **승인**
2. 승인 후 DEPLOY 페이지에서 카나리 배포 생성 완료
3. 대시보드에서 `deployment_id` 복사

## 설치

```bash
pip install verum
```

## 환경 변수 설정

```bash
cp .env.example .env
# .env 편집: VERUM_API_URL, VERUM_API_KEY, VERUM_DEPLOYMENT_ID 입력
```

## 적용

`before.py`와 `after.py`를 비교하세요. 변경 사항은 3가지입니다:

1. `verum.Client()` 초기화
2. LLM 호출 전 `verum.retrieve()`로 RAG 컨텍스트 조회
3. `verum.chat()`으로 메시지를 감싸서 10% 트래픽을 CoT variant으로 라우팅

## 검증

ArcanaInsight 배포 후 Verum 대시보드의 `/deploy/[deployment_id]` 페이지에서:
- `total_calls` 증가 확인
- 트래픽 분할 슬라이더로 10% → 50% → 100% 조정 가능
- `error_rate`가 급등하면 [롤백] 버튼으로 즉시 원복

## Phase 3 완료 조건

`docs/WEEKLY.md`에 다음을 기록하세요:
- 카나리 배포 후 최소 10콜 확인
- CoT variant 프롬프트가 정상 작동
- RAG 컨텍스트가 응답에 반영됨
```

- [ ] **Step 5: Update ROADMAP**

In `docs/ROADMAP.md`, update F-3.10 to 🔲 with note:
> "Verum delivers: examples/arcana-integration/. xzawed applies to ArcanaInsight manually."

- [ ] **Step 6: Run full test suite to confirm nothing is broken**

```bash
cd apps/api
PYTHONPATH=. pytest tests/ -v --cov=src.loop --cov-report=term-missing
```

Expected: coverage ≥ 45% (CI threshold), all tests pass.

- [ ] **Step 7: Commit**

```bash
git add examples/arcana-integration/ docs/ROADMAP.md
git commit -m "feat(deploy): F-3.10 ArcanaInsight Verum integration example and guide"
```

---

## Self-Review

### Spec Coverage Check

| Deliverable | Task |
|-------------|------|
| F-0.7 CI (pylint + path fix) | Task 1 ✅ |
| F-1.4 ArcanaInsight ANALYZE validation | Task 2 ✅ |
| F-1.8 REST endpoints (analyze, infer) | Task 3 ✅ |
| F-3.4 metric_profile.py + Alembic migration | Task 4 ✅ |
| F-3.5 GENERATE API + dashboard page | Task 5 ✅ |
| F-3.6 DEPLOY engine (models, engine, repository) | Task 6 ✅ |
| F-3.7 DEPLOY API + dashboard page | Task 6 ✅ |
| F-3.8 Python SDK (Client, cache, router) | Task 7 ✅ |
| F-3.9 TypeScript SDK (VerumClient, cache, router) | Task 8 ✅ |
| F-3.10 ArcanaInsight integration example | Task 9 ✅ |

### Notes for Execution

- Tasks 2+3 can run in parallel (independent)
- Tasks 4+5 can run in parallel (Task 5 depends on Task 4's migration, but schema.ts changes in Task 5 Step 1 must come after Task 4's Alembic migration)
- Tasks 7+8 can run in parallel (independent)
- Task 9 requires Tasks 7 and 8 complete first (SDK must exist before writing examples)
- The `VERUM_API_KEY` environment variable must be set in Railway before SDK config endpoint will work

---

_Maintainer: xzawed | Last updated: 2026-04-22_
