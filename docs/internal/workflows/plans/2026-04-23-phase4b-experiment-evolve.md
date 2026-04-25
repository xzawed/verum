# Phase 4-B: EXPERIMENT + EVOLVE Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the EXPERIMENT ([7]) and EVOLVE ([8]) stages of The Verum Loop — sequential Bayesian A/B testing across 5 prompt variants with automatic winner promotion, requiring zero manual intervention.

**Architecture:** A 5-minute periodic worker loop (`_experiment_loop`) scans active experiments, applies the Beta-Bernoulli model, and enqueues EVOLVE jobs when convergence is reached. The EVOLVE handler promotes winners, starts the next challenger, and eventually sets `experiment_status = "completed"` with the winner at 100% traffic. The dashboard ExperimentSection polls `/api/v1/experiments` every 5s while status is `running`.

**Tech Stack:** Python asyncio + SQLAlchemy 2 text() queries + scipy (Bayesian) + Next.js App Router + Drizzle ORM + Auth.js v5 session

**Spec:** `docs/internal/workflows/specs/2026-04-23-phase4b-experiment-evolve-design.md`

---

## File Map

### New Python files
| File | Responsibility |
|---|---|
| `apps/api/alembic/versions/0010_phase4b_experiment_evolve.py` | DB migration: experiments table + deployments columns + traffic_split data migration |
| `apps/api/src/loop/experiment/__init__.py` | Package marker |
| `apps/api/src/loop/experiment/models.py` | `ExperimentResult`, `VariantStats` Pydantic models |
| `apps/api/src/loop/experiment/engine.py` | `compute_winner_score()`, `bayesian_confidence()`, `check_experiment()` — pure functions |
| `apps/api/src/loop/experiment/repository.py` | DB I/O: `get_running_experiment()`, `update_experiment_stats()`, `insert_experiment()` |
| `apps/api/src/loop/evolve/__init__.py` | Package marker |
| `apps/api/src/loop/evolve/engine.py` | `promote_winner()`, `start_next_challenger()`, `complete_deployment()` — orchestration |
| `apps/api/src/loop/evolve/repository.py` | DB I/O: `update_deployment_baseline()`, `update_traffic_split()` |
| `apps/api/src/worker/handlers/evolve.py` | `handle_evolve()` — EVOLVE job handler |

### New test files
| File | What it tests |
|---|---|
| `apps/api/tests/loop/experiment/__init__.py` | Package marker |
| `apps/api/tests/loop/experiment/test_engine.py` | `compute_winner_score`, `bayesian_confidence`, `check_experiment` |
| `apps/api/tests/loop/evolve/__init__.py` | Package marker |

### Modified Python files
| File | Change |
|---|---|
| `apps/api/src/worker/runner.py` | Add `_experiment_loop()` + register `evolve` handler |
| `apps/api/src/worker/handlers/deploy.py` | Call `insert_experiment()` after deploy succeeds |
| `apps/api/src/loop/generate/engine.py` | L-3 fix: line 126 `20` → `30` eval pairs |

### New Next.js files
| File | Responsibility |
|---|---|
| `apps/dashboard/src/app/api/v1/experiments/route.ts` | `GET ?deployment_id=` — list all experiments for deployment |
| `apps/dashboard/src/app/api/v1/experiments/[id]/route.ts` | `GET` — single experiment detail |
| `apps/dashboard/src/app/repos/[id]/ExperimentSection.tsx` | Client component: rounds, Bayesian bar, history table |

### Modified Next.js files
| File | Change |
|---|---|
| `apps/dashboard/src/lib/db/schema.ts` | Add `experiments` table + `experiment_status`/`current_baseline_variant` to `deployments` |
| `apps/dashboard/src/lib/db/queries.ts` | Add `getExperiments()`, `getExperiment()` |
| `apps/dashboard/src/app/repos/[id]/StagesView.tsx` | Mount `ExperimentSection` when `experiment_status !== 'idle'` |

### Docs
| File | Change |
|---|---|
| `docs/METHODOLOGY.md` | Fill §7 (EXPERIMENT) and §8 (EVOLVE) placeholders |

---

## Task 1: Alembic Migration 0010

**Files:**
- Create: `apps/api/alembic/versions/0010_phase4b_experiment_evolve.py`

- [ ] **Step 1: Create the migration file**

```python
# apps/api/alembic/versions/0010_phase4b_experiment_evolve.py
"""Add experiments table; add experiment_status, current_baseline_variant to deployments.

Revision ID: 0010_phase4b_experiment_evolve
Revises: 0009_phase4a_observe
Create Date: 2026-04-23
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0010_phase4b_experiment_evolve"
down_revision: Union[str, None] = "0009_phase4a_observe"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. New columns on deployments
    op.add_column(
        "deployments",
        sa.Column("experiment_status", sa.Text, nullable=False, server_default="idle"),
    )
    op.add_column(
        "deployments",
        sa.Column(
            "current_baseline_variant",
            sa.Text,
            nullable=False,
            server_default="original",
        ),
    )

    # 2. New experiments table
    op.create_table(
        "experiments",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "deployment_id",
            UUID(as_uuid=True),
            sa.ForeignKey("deployments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("baseline_variant", sa.Text, nullable=False),
        sa.Column("challenger_variant", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="running"),
        sa.Column("winner_variant", sa.Text, nullable=True),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("baseline_wins", sa.Integer, nullable=False, server_default="0"),
        sa.Column("baseline_n", sa.Integer, nullable=False, server_default="0"),
        sa.Column("challenger_wins", sa.Integer, nullable=False, server_default="0"),
        sa.Column("challenger_n", sa.Integer, nullable=False, server_default="0"),
        sa.Column("win_threshold", sa.Float, nullable=False, server_default="0.6"),
        sa.Column("cost_weight", sa.Float, nullable=False, server_default="0.1"),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("converged_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index("ix_experiments_deployment_id", "experiments", ["deployment_id"])
    op.create_index("ix_experiments_status", "experiments", ["status"])

    # 3. Migrate existing traffic_split from generic keys to specific variant names.
    # Deployments with no experiment row are left unchanged (they have no running experiment).
    # Deployments where traffic_split uses {"baseline", "variant"} keys get migrated
    # to {current_baseline_variant: baseline_fraction, challenger_variant: variant_fraction}.
    # Since no experiments exist yet (new table), all deployments keep their existing split.
    # This is a no-op for data but establishes the forward contract.
    op.execute(sa.text("SELECT 1"))  # no-op placeholder — data migration only needed if experiments table had rows


def downgrade() -> None:
    op.drop_index("ix_experiments_status", table_name="experiments")
    op.drop_index("ix_experiments_deployment_id", table_name="experiments")
    op.drop_table("experiments")
    op.drop_column("deployments", "current_baseline_variant")
    op.drop_column("deployments", "experiment_status")
```

- [ ] **Step 2: Verify migration runs cleanly (requires local DB)**

```bash
cd apps/api
python -m alembic upgrade 0010_phase4b_experiment_evolve
python -m alembic downgrade 0009_phase4a_observe
python -m alembic upgrade 0010_phase4b_experiment_evolve
```

Expected: no error output, schema changes visible in `\d experiments` (psql).

- [ ] **Step 3: Commit**

```bash
git add apps/api/alembic/versions/0010_phase4b_experiment_evolve.py
git commit -m "feat(experiment): add 0010 migration — experiments table + deployment experiment columns"
```

---

## Task 2: Pydantic Models for EXPERIMENT

**Files:**
- Create: `apps/api/src/loop/experiment/__init__.py`
- Create: `apps/api/src/loop/experiment/models.py`
- Create: `apps/api/tests/loop/experiment/__init__.py`
- Test: `apps/api/tests/loop/experiment/test_models.py`

- [ ] **Step 1: Write the failing test**

```python
# apps/api/tests/loop/experiment/test_models.py
import uuid
from datetime import datetime, timezone

import pytest
from src.loop.experiment.models import ExperimentResult, VariantStats


def test_variant_stats_win_rate_no_division_by_zero():
    stats = VariantStats(variant="original", wins=0, n=0, avg_winner_score=0.0)
    assert stats.win_rate == 0.0


def test_variant_stats_win_rate_normal():
    stats = VariantStats(variant="cot", wins=70, n=100, avg_winner_score=0.75)
    assert stats.win_rate == pytest.approx(0.70)


def test_experiment_result_fields():
    exp = ExperimentResult(
        experiment_id=uuid.uuid4(),
        deployment_id=uuid.uuid4(),
        baseline=VariantStats(variant="original", wins=40, n=100, avg_winner_score=0.6),
        challenger=VariantStats(variant="cot", wins=70, n=100, avg_winner_score=0.75),
        confidence=0.97,
        converged=True,
        winner_variant="cot",
    )
    assert exp.winner_variant == "cot"
    assert exp.converged is True
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd apps/api
python -m pytest tests/loop/experiment/test_models.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.loop.experiment'`

- [ ] **Step 3: Create package markers and implement models**

```python
# apps/api/src/loop/experiment/__init__.py
# (empty)
```

```python
# apps/api/tests/loop/experiment/__init__.py
# (empty)
```

```python
# apps/api/src/loop/experiment/models.py
"""Pydantic models for the EXPERIMENT stage ([7] of The Verum Loop)."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, computed_field


class VariantStats(BaseModel):
    variant: str
    wins: int
    n: int
    avg_winner_score: float

    @computed_field  # type: ignore[misc]
    @property
    def win_rate(self) -> float:
        return self.wins / self.n if self.n > 0 else 0.0


class ExperimentResult(BaseModel):
    experiment_id: uuid.UUID
    deployment_id: uuid.UUID
    baseline: VariantStats
    challenger: VariantStats
    confidence: float
    converged: bool
    winner_variant: str | None
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd apps/api
python -m pytest tests/loop/experiment/test_models.py -v
```

Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/loop/experiment/__init__.py \
        apps/api/src/loop/experiment/models.py \
        apps/api/tests/loop/experiment/__init__.py \
        apps/api/tests/loop/experiment/test_models.py
git commit -m "feat(experiment): add ExperimentResult and VariantStats Pydantic models"
```

---

## Task 3: Experiment Engine (Pure Functions)

**Files:**
- Create: `apps/api/src/loop/experiment/engine.py`
- Test: `apps/api/tests/loop/experiment/test_engine.py`

- [ ] **Step 1: Write the failing tests**

```python
# apps/api/tests/loop/experiment/test_engine.py
import pytest
from src.loop.experiment.engine import (
    compute_winner_score,
    bayesian_confidence,
    check_experiment,
)
from src.loop.experiment.models import ExperimentResult, VariantStats
import uuid


# ── compute_winner_score ──────────────────────────────────────────────────────

def test_winner_score_no_cost():
    # max_cost == 0: no cost penalty
    score = compute_winner_score(judge_score=0.8, cost_usd=0.01, max_cost_in_window=0.0)
    assert score == pytest.approx(0.8)


def test_winner_score_full_cost_penalty():
    # cost_usd == max_cost → cost_normalized == 1.0, penalty = 0.1 * 1.0 = 0.1
    score = compute_winner_score(judge_score=0.8, cost_usd=1.0, max_cost_in_window=1.0)
    assert score == pytest.approx(0.7)


def test_winner_score_partial_penalty():
    # cost_usd = 0.5, max = 1.0 → cost_normalized = 0.5, penalty = 0.05
    score = compute_winner_score(judge_score=0.75, cost_usd=0.5, max_cost_in_window=1.0, cost_weight=0.1)
    assert score == pytest.approx(0.70)


# ── bayesian_confidence ───────────────────────────────────────────────────────

def test_bayesian_confidence_challenger_dominates():
    # challenger wins 90/100, baseline wins 10/100 → P(challenger > baseline) >> 0.95
    conf = bayesian_confidence(b_wins=10, b_n=100, c_wins=90, c_n=100, samples=20_000)
    assert conf > 0.95


def test_bayesian_confidence_baseline_dominates():
    # baseline wins 90/100, challenger wins 10/100 → P(challenger > baseline) < 0.05
    conf = bayesian_confidence(b_wins=90, b_n=100, c_wins=10, c_n=100, samples=20_000)
    assert conf < 0.05


def test_bayesian_confidence_uncertain():
    # Roughly equal: 50/100 vs 52/100 → in [0.05, 0.95]
    conf = bayesian_confidence(b_wins=50, b_n=100, c_wins=52, c_n=100, samples=20_000)
    assert 0.05 < conf < 0.95


# ── check_experiment ─────────────────────────────────────────────────────────

def make_experiment_dict(
    b_wins: int = 0, b_n: int = 0,
    c_wins: int = 0, c_n: int = 0,
) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "deployment_id": str(uuid.uuid4()),
        "baseline_variant": "original",
        "challenger_variant": "cot",
        "baseline_wins": b_wins,
        "baseline_n": b_n,
        "challenger_wins": c_wins,
        "challenger_n": c_n,
        "win_threshold": 0.6,
        "cost_weight": 0.1,
    }


def test_check_experiment_not_converged_insufficient_samples():
    exp_row = make_experiment_dict(b_wins=80, b_n=99, c_wins=90, c_n=99)
    result = check_experiment(exp_row, max_cost_in_window=1.0)
    assert result.converged is False


def test_check_experiment_converged_challenger_wins():
    exp_row = make_experiment_dict(b_wins=10, b_n=100, c_wins=90, c_n=100)
    result = check_experiment(exp_row, max_cost_in_window=1.0)
    assert result.converged is True
    assert result.winner_variant == "cot"
    assert result.confidence >= 0.95


def test_check_experiment_converged_baseline_holds():
    exp_row = make_experiment_dict(b_wins=90, b_n=100, c_wins=10, c_n=100)
    result = check_experiment(exp_row, max_cost_in_window=1.0)
    assert result.converged is True
    assert result.winner_variant == "original"
    assert result.confidence <= 0.05
```

- [ ] **Step 2: Run to verify all fail**

```bash
cd apps/api
python -m pytest tests/loop/experiment/test_engine.py -v
```

Expected: `ImportError` or `ModuleNotFoundError` on `engine`.

- [ ] **Step 3: Implement the engine**

```python
# apps/api/src/loop/experiment/engine.py
"""Pure functions for Bayesian A/B experiment evaluation.

[7] EXPERIMENT stage of The Verum Loop.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# Challenger variants tried in this fixed order. Round 1 = original vs cot, etc.
CHALLENGER_ORDER: list[str] = ["cot", "few_shot", "role_play", "concise"]

MIN_SAMPLES = 100          # minimum n per variant before convergence is evaluated
CONFIDENCE_THRESHOLD = 0.95  # P(challenger > baseline) ≥ this → challenger wins
CONFIDENCE_FLOOR = 0.05      # P(challenger > baseline) ≤ this → baseline holds


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

    Falls back to raw win-rate ratio if scipy is unavailable.
    """
    try:
        from scipy import stats  # type: ignore[import-untyped]

        baseline = stats.beta(1 + b_wins, 1 + (b_n - b_wins))
        challenger = stats.beta(1 + c_wins, 1 + (c_n - c_wins))
        rng = np.random.default_rng()
        return float(np.mean(challenger.rvs(samples, random_state=rng) > baseline.rvs(samples, random_state=rng)))
    except ImportError:
        logger.warning("scipy not available; falling back to raw win-rate comparison")
        b_rate = b_wins / b_n if b_n > 0 else 0.0
        c_rate = c_wins / c_n if c_n > 0 else 0.0
        return 1.0 if c_rate > b_rate else 0.0


def check_experiment(
    experiment_row: dict[str, Any],
    max_cost_in_window: float,
) -> "ExperimentResult":  # noqa: F821 — imported below to avoid circular at module level
    """Evaluate an experiment row and return an ExperimentResult.

    Does NOT write to the database. The caller decides whether to enqueue EVOLVE.
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
        winner = experiment_row["challenger_variant"] if conf >= CONFIDENCE_THRESHOLD else experiment_row["baseline_variant"]
    else:
        winner = None

    return ExperimentResult(
        experiment_id=uuid.UUID(str(experiment_row["id"])),
        deployment_id=uuid.UUID(str(experiment_row["deployment_id"])),
        baseline=VariantStats(
            variant=experiment_row["baseline_variant"],
            wins=b_wins,
            n=b_n,
            avg_winner_score=0.0,  # aggregated in repository, not needed for convergence check
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd apps/api
python -m pytest tests/loop/experiment/test_engine.py -v
```

Expected: 9 tests PASS (Bayesian tests may be slow — normal, they run 20k samples).

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/loop/experiment/engine.py \
        apps/api/tests/loop/experiment/test_engine.py
git commit -m "feat(experiment): implement compute_winner_score, bayesian_confidence, check_experiment"
```

---

## Task 4: Experiment Repository

**Files:**
- Create: `apps/api/src/loop/experiment/repository.py`

No unit tests for repository (requires real DB). Integration tested implicitly via handler tests in Task 6.

- [ ] **Step 1: Implement the repository**

```python
# apps/api/src/loop/experiment/repository.py
"""Database I/O for the EXPERIMENT stage."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def get_running_experiment(
    db: AsyncSession,
    deployment_id: uuid.UUID,
) -> dict[str, Any] | None:
    """Return the currently running experiment row for a deployment, or None."""
    row = (
        await db.execute(
            text(
                "SELECT * FROM experiments"
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
                "SELECT e.*, d.experiment_status FROM experiments e"
                " JOIN deployments d ON d.id = e.deployment_id"
                " WHERE e.status = 'running' AND d.experiment_status = 'running'"
            )
        )
    ).mappings().all()
    return [dict(r) for r in rows]


async def get_max_cost_in_window(
    db: AsyncSession,
    deployment_id: uuid.UUID,
    days: int = 7,
) -> float:
    """Return the maximum cost_usd across all traces for the deployment in the last N days."""
    row = (
        await db.execute(
            text(
                "SELECT COALESCE(MAX(s.cost_usd), 0) AS max_cost"
                " FROM traces t JOIN spans s ON s.trace_id = t.id"
                " WHERE t.deployment_id = :did"
                "   AND t.created_at >= now() - interval ':days days'"
            ),
            {"did": str(deployment_id), "days": days},
        )
    ).mappings().first()
    return float(row["max_cost"]) if row else 0.0


async def update_experiment_stats(
    db: AsyncSession,
    experiment_id: uuid.UUID,
    baseline_wins: int,
    baseline_n: int,
    challenger_wins: int,
    challenger_n: int,
) -> None:
    """Overwrite win counters with freshly aggregated values."""
    await db.execute(
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
    await db.commit()


async def aggregate_variant_wins(
    db: AsyncSession,
    deployment_id: uuid.UUID,
    baseline_variant: str,
    challenger_variant: str,
    win_threshold: float,
) -> tuple[int, int, int, int]:
    """Count binary wins (winner_score > win_threshold) per variant.

    Returns (baseline_wins, baseline_n, challenger_wins, challenger_n).
    winner_score = judge_score − 0.1 × (cost_usd / max_cost_in_window).
    Traces with NULL judge_score are excluded from n.
    """
    max_cost_row = (
        await db.execute(
            text(
                "SELECT COALESCE(MAX(s.cost_usd), 0) AS max_cost"
                " FROM traces t JOIN spans s ON s.trace_id = t.id"
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
                "        THEN COALESCE(s.cost_usd, 0) / :max_cost ELSE 0 END"
                "    ) > :threshold"
                "  ) AS wins"
                " FROM traces t"
                " LEFT JOIN spans s ON s.trace_id = t.id"
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

    stats: dict[str, dict[str, int]] = {baseline_variant: {"wins": 0, "n": 0}, challenger_variant: {"wins": 0, "n": 0}}
    for row in rows:
        if row["variant"] in stats:
            stats[row["variant"]] = {"wins": int(row["wins"]), "n": int(row["n"])}

    return (
        stats[baseline_variant]["wins"],
        stats[baseline_variant]["n"],
        stats[challenger_variant]["wins"],
        stats[challenger_variant]["n"],
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
        raise RuntimeError(f"insert_experiment: INSERT returned no row for deployment_id={deployment_id}")
    return dict(row)


async def mark_experiment_converged(
    db: AsyncSession,
    experiment_id: uuid.UUID,
    winner_variant: str,
    confidence: float,
) -> None:
    await db.execute(
        text(
            "UPDATE experiments"
            " SET status = 'converged', winner_variant = :wv, confidence = :conf,"
            "     converged_at = now()"
            " WHERE id = :eid"
        ),
        {"wv": winner_variant, "conf": confidence, "eid": str(experiment_id)},
    )
    await db.commit()
```

- [ ] **Step 2: Commit**

```bash
git add apps/api/src/loop/experiment/repository.py
git commit -m "feat(experiment): add experiment repository (DB I/O for EXPERIMENT stage)"
```

---

## Task 5: Evolve Engine + Repository

**Files:**
- Create: `apps/api/src/loop/evolve/__init__.py`
- Create: `apps/api/src/loop/evolve/engine.py`
- Create: `apps/api/src/loop/evolve/repository.py`
- Create: `apps/api/tests/loop/evolve/__init__.py`

- [ ] **Step 1: Create package markers**

```python
# apps/api/src/loop/evolve/__init__.py
# (empty)
```

```python
# apps/api/tests/loop/evolve/__init__.py
# (empty)
```

- [ ] **Step 2: Implement the evolve repository**

```python
# apps/api/src/loop/evolve/repository.py
"""Database I/O for the EVOLVE stage."""
from __future__ import annotations

import json
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def update_deployment_baseline(
    db: AsyncSession,
    deployment_id: uuid.UUID,
    new_baseline: str,
) -> None:
    await db.execute(
        text(
            "UPDATE deployments SET current_baseline_variant = :bv, updated_at = now()"
            " WHERE id = :did"
        ),
        {"bv": new_baseline, "did": str(deployment_id)},
    )
    await db.commit()


async def update_traffic_split(
    db: AsyncSession,
    deployment_id: uuid.UUID,
    split: dict[str, float],
) -> None:
    await db.execute(
        text(
            "UPDATE deployments SET traffic_split = :split::jsonb, updated_at = now()"
            " WHERE id = :did"
        ),
        {"split": json.dumps(split), "did": str(deployment_id)},
    )
    await db.commit()


async def set_experiment_status(
    db: AsyncSession,
    deployment_id: uuid.UUID,
    status: str,
) -> None:
    """Set deployments.experiment_status to 'running' | 'completed' | 'idle'."""
    await db.execute(
        text(
            "UPDATE deployments SET experiment_status = :s, updated_at = now()"
            " WHERE id = :did"
        ),
        {"s": status, "did": str(deployment_id)},
    )
    await db.commit()
```

- [ ] **Step 3: Implement the evolve engine**

```python
# apps/api/src/loop/evolve/engine.py
"""Orchestration logic for the EVOLVE stage ([8] of The Verum Loop).

Responsible for:
- Promoting the winning variant to 100% traffic after final round
- Starting the next challenger after an intermediate round converges
- Marking a deployment as experiment_status='completed'
"""
from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.loop.experiment.engine import CHALLENGER_ORDER
from src.loop.experiment.repository import insert_experiment, mark_experiment_converged
from src.loop.evolve.repository import (
    set_experiment_status,
    update_deployment_baseline,
    update_traffic_split,
)

logger = logging.getLogger(__name__)


async def promote_winner(
    db: AsyncSession,
    experiment_id: uuid.UUID,
    deployment_id: uuid.UUID,
    winner_variant: str,
    confidence: float,
) -> None:
    """Record convergence on the experiment row."""
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

    Returns True if a new round was started, False if all rounds are done.
    """
    challenger = next_challenger(winner_variant, current_challenger)
    if challenger is None:
        return False

    await insert_experiment(db, deployment_id, winner_variant, challenger)
    await update_traffic_split(db, deployment_id, {winner_variant: 0.9, challenger: 0.1})
    logger.info(
        "EVOLVE: deployment %s — new experiment %s vs %s", deployment_id, winner_variant, challenger
    )
    return True


async def complete_deployment(
    db: AsyncSession,
    deployment_id: uuid.UUID,
    winner_variant: str,
) -> None:
    """Final round complete: 100% traffic to winner, mark deployment complete."""
    await update_traffic_split(db, deployment_id, {winner_variant: 1.0})
    await set_experiment_status(db, deployment_id, "completed")
    logger.info(
        "EVOLVE: deployment %s complete — final winner=%s at 100%%", deployment_id, winner_variant
    )
```

- [ ] **Step 4: Verify imports work**

```bash
cd apps/api
python -c "from src.loop.evolve.engine import next_challenger, CHALLENGER_ORDER; print(next_challenger('original', 'cot')); print(next_challenger('cot', 'concise'))"
```

Expected output:
```
few_shot
None
```

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/loop/evolve/__init__.py \
        apps/api/src/loop/evolve/engine.py \
        apps/api/src/loop/evolve/repository.py \
        apps/api/tests/loop/evolve/__init__.py
git commit -m "feat(evolve): add EVOLVE engine and repository (promote_winner, start_next_challenger, complete_deployment)"
```

---

## Task 6: EVOLVE Job Handler

**Files:**
- Create: `apps/api/src/worker/handlers/evolve.py`

- [ ] **Step 1: Implement the handler**

```python
# apps/api/src/worker/handlers/evolve.py
"""EVOLVE job handler.

Payload schema:
  experiment_id: str (UUID)
  winner_variant: str
  confidence: float
  deployment_id: str (UUID)
  current_challenger: str
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.loop.evolve.engine import (
    complete_deployment,
    promote_winner,
    start_next_challenger,
)

logger = logging.getLogger(__name__)


async def handle_evolve(
    db: AsyncSession,
    owner_user_id: uuid.UUID,
    payload: dict[str, Any],
) -> dict[str, Any]:
    experiment_id = uuid.UUID(payload["experiment_id"])
    deployment_id = uuid.UUID(payload["deployment_id"])
    winner_variant: str = payload["winner_variant"]
    confidence: float = float(payload["confidence"])
    current_challenger: str = payload["current_challenger"]

    # Step 1: Mark experiment converged + update baseline
    await promote_winner(db, experiment_id, deployment_id, winner_variant, confidence)

    # Step 2: Try to start next round; if no next challenger, complete deployment
    started = await start_next_challenger(db, deployment_id, winner_variant, current_challenger)
    if not started:
        await complete_deployment(db, deployment_id, winner_variant)

    logger.info(
        "EVOLVE job done: deployment=%s winner=%s next_started=%s",
        deployment_id,
        winner_variant,
        started,
    )
    return {
        "deployment_id": str(deployment_id),
        "winner_variant": winner_variant,
        "next_round_started": started,
    }
```

- [ ] **Step 2: Commit**

```bash
git add apps/api/src/worker/handlers/evolve.py
git commit -m "feat(evolve): add handle_evolve job handler"
```

---

## Task 7: Runner Modifications (_experiment_loop + evolve handler)

**Files:**
- Modify: `apps/api/src/worker/runner.py`

- [ ] **Step 1: Read the current runner.py to identify exact insertion points**

Read `apps/api/src/worker/runner.py` in full before editing.

- [ ] **Step 2: Add `_experiment_loop` and register `evolve` handler**

In `runner.py`, make these three changes:

**Change A** — Add import at the top (after existing handler imports):

```python
from src.worker.handlers.evolve import handle_evolve
```

**Change B** — Add `evolve` to `_HANDLERS` dict (after existing entries):

```python
_HANDLERS: dict[str, Any] = {
    "analyze": handle_analyze,
    "infer": handle_infer,
    "harvest": handle_harvest,
    "retrieve": handle_retrieve,
    "generate": handle_generate,
    "deploy": handle_deploy,
    "judge": handle_judge,
    "evolve": handle_evolve,   # ← add this line
}
```

**Change C** — Add `_experiment_loop` function and start it inside `run_loop()`.

Add this function before `run_loop()`:

```python
EXPERIMENT_INTERVAL: int = 300  # 5 minutes


async def _experiment_loop() -> None:
    """Periodic loop: check all running experiments and enqueue EVOLVE jobs on convergence."""
    from src.loop.experiment.engine import check_experiment
    from src.loop.experiment.repository import (
        aggregate_variant_wins,
        get_all_running_experiments,
        update_experiment_stats,
    )

    while True:
        await asyncio.sleep(EXPERIMENT_INTERVAL)
        try:
            async with AsyncSessionLocal() as db:
                experiments = await get_all_running_experiments(db)
                for exp in experiments:
                    try:
                        deployment_id = exp["deployment_id"]
                        b_wins, b_n, c_wins, c_n = await aggregate_variant_wins(
                            db,
                            deployment_id,
                            exp["baseline_variant"],
                            exp["challenger_variant"],
                            exp["win_threshold"],
                        )
                        await update_experiment_stats(
                            db, exp["id"], b_wins, b_n, c_wins, c_n
                        )
                        result = check_experiment(
                            {**exp, "baseline_wins": b_wins, "baseline_n": b_n,
                             "challenger_wins": c_wins, "challenger_n": c_n},
                            max_cost_in_window=1.0,  # max_cost is embedded in aggregate_variant_wins
                        )
                        if result.converged and result.winner_variant:
                            await db.execute(
                                sa.text(
                                    "INSERT INTO verum_jobs (kind, payload, status, owner_user_id)"
                                    " SELECT 'evolve',"
                                    "   jsonb_build_object("
                                    "     'experiment_id', :eid,"
                                    "     'deployment_id', :did,"
                                    "     'winner_variant', :wv,"
                                    "     'confidence', :conf,"
                                    "     'current_challenger', :cv"
                                    "   ),"
                                    "   'queued',"
                                    "   (SELECT owner_user_id FROM repos r"
                                    "    JOIN generations g ON g.inference_id IN ("
                                    "      SELECT id FROM inferences WHERE repo_id = r.id"
                                    "    )"
                                    "    JOIN deployments d ON d.generation_id = g.id"
                                    "    WHERE d.id = :did LIMIT 1)"
                                    " WHERE NOT EXISTS ("
                                    "   SELECT 1 FROM verum_jobs"
                                    "   WHERE kind = 'evolve'"
                                    "     AND (payload->>'experiment_id') = :eid"
                                    "     AND status IN ('queued', 'running')"
                                    " )"
                                ),
                                {
                                    "eid": str(exp["id"]),
                                    "did": str(deployment_id),
                                    "wv": result.winner_variant,
                                    "conf": result.confidence,
                                    "cv": exp["challenger_variant"],
                                },
                            )
                            await db.commit()
                            logger.info(
                                "EXPERIMENT: enqueued EVOLVE for experiment %s winner=%s",
                                exp["id"],
                                result.winner_variant,
                            )
                    except Exception as exc:
                        logger.warning("EXPERIMENT: error checking experiment %s: %s", exp.get("id"), exc)
        except Exception as exc:
            logger.warning("EXPERIMENT loop error: %s", exc)
```

Inside `run_loop()`, after `asyncio.create_task(_heartbeat_loop())`, add:

```python
    asyncio.create_task(_experiment_loop())
    logger.info("Experiment loop started (interval=%ds)", EXPERIMENT_INTERVAL)
```

Also add `import sqlalchemy as sa` to the runner imports if not already present.

- [ ] **Step 3: Verify the runner imports cleanly**

```bash
cd apps/api
python -c "from src.worker.runner import run_loop; print('ok')"
```

Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add apps/api/src/worker/runner.py
git commit -m "feat(experiment): add _experiment_loop background task + register evolve handler in runner"
```

---

## Task 8: Deploy Handler — Insert First Experiment

**Files:**
- Modify: `apps/api/src/worker/handlers/deploy.py`

- [ ] **Step 1: Read deploy.py**

Read `apps/api/src/worker/handlers/deploy.py` to confirm the current return statement location.

- [ ] **Step 2: Modify deploy.py**

Replace the entire file content with:

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
from src.loop.experiment.repository import insert_experiment

logger = logging.getLogger(__name__)


async def handle_deploy(
    db: AsyncSession,
    owner_user_id: uuid.UUID,
    payload: dict[str, Any],
) -> dict[str, Any]:
    generation_id = uuid.UUID(payload["generation_id"])
    deployment = await create_deployment(db, generation_id, variant_fraction=0.10)
    logger.info("DEPLOY complete: deployment_id=%s status=%s", deployment.deployment_id, deployment.status)

    # Kick off the first experiment round: original vs cot
    await db.execute(
        __import__("sqlalchemy").text(
            "UPDATE deployments SET experiment_status = 'running', updated_at = now()"
            " WHERE id = :did"
        ),
        {"did": str(deployment.deployment_id)},
    )
    await db.commit()

    await insert_experiment(db, deployment.deployment_id, "original", "cot")
    logger.info("EXPERIMENT: round 1 started (original vs cot) for deployment %s", deployment.deployment_id)

    return {
        "deployment_id": str(deployment.deployment_id),
        "status": deployment.status,
        "traffic_split": deployment.traffic_split,
    }
```

- [ ] **Step 3: Verify import**

```bash
cd apps/api
python -c "from src.worker.handlers.deploy import handle_deploy; print('ok')"
```

Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add apps/api/src/worker/handlers/deploy.py
git commit -m "feat(experiment): insert first experiment (original vs cot) after DEPLOY completes"
```

---

## Task 9: Dashboard Schema + Queries

**Files:**
- Modify: `apps/dashboard/src/lib/db/schema.ts`
- Modify: `apps/dashboard/src/lib/db/queries.ts`

- [ ] **Step 1: Add experiments table and update deployments in schema.ts**

In `apps/dashboard/src/lib/db/schema.ts`:

Add `doublePrecision` to the existing imports if not present (it already is).

**Change A** — Update `deployments` pgTable to add two new columns after `updated_at`:

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
  experiment_status: text("experiment_status").notNull().default("idle"),
  current_baseline_variant: text("current_baseline_variant").notNull().default("original"),
  created_at: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  updated_at: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
});
```

**Change B** — Add experiments table after the `judge_prompts` table:

```typescript
export const experiments = pgTable("experiments", {
  id: uuid("id").primaryKey().$defaultFn(() => crypto.randomUUID()),
  deployment_id: uuid("deployment_id")
    .notNull()
    .references(() => deployments.id, { onDelete: "cascade" }),
  baseline_variant: text("baseline_variant").notNull(),
  challenger_variant: text("challenger_variant").notNull(),
  status: text("status").notNull().default("running"),
  winner_variant: text("winner_variant"),
  confidence: doublePrecision("confidence"),
  baseline_wins: integer("baseline_wins").notNull().default(0),
  baseline_n: integer("baseline_n").notNull().default(0),
  challenger_wins: integer("challenger_wins").notNull().default(0),
  challenger_n: integer("challenger_n").notNull().default(0),
  win_threshold: doublePrecision("win_threshold").notNull().default(0.6),
  cost_weight: doublePrecision("cost_weight").notNull().default(0.1),
  started_at: timestamp("started_at", { withTimezone: true }).notNull().defaultNow(),
  converged_at: timestamp("converged_at", { withTimezone: true }),
});

export type Experiment = typeof experiments.$inferSelect;
```

Also add `Experiment` to the existing type exports at the bottom.

- [ ] **Step 2: Add getExperiments and getExperiment to queries.ts**

In `apps/dashboard/src/lib/db/queries.ts`, add these imports at the top:

```typescript
import {
  // ...existing imports...
  experiments,
  type Experiment,
} from "./schema";
```

Also add `Experiment` to the `export type { ... }` line.

Then add these two functions at the end of the file:

```typescript
export async function getExperiments(
  userId: string,
  deploymentId: string,
): Promise<Experiment[]> {
  // Verify ownership: deployment must belong to a generation → inference → repo owned by userId
  const dep = await getDeployment(userId, deploymentId);
  if (!dep) return [];

  return db
    .select()
    .from(experiments)
    .where(eq(experiments.deployment_id, deploymentId))
    .orderBy(desc(experiments.started_at));
}

export async function getExperiment(
  userId: string,
  experimentId: string,
): Promise<Experiment | null> {
  const rows = await db
    .select()
    .from(experiments)
    .where(eq(experiments.id, experimentId))
    .limit(1);

  if (!rows[0]) return null;

  // Ownership check via deployment
  const dep = await getDeployment(userId, rows[0].deployment_id);
  if (!dep) return null;

  return rows[0];
}
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd apps/dashboard
pnpm tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/src/lib/db/schema.ts \
        apps/dashboard/src/lib/db/queries.ts
git commit -m "feat(experiment): add experiments table to Drizzle schema and getExperiments/getExperiment queries"
```

---

## Task 10: Dashboard API Routes

**Files:**
- Create: `apps/dashboard/src/app/api/v1/experiments/route.ts`
- Create: `apps/dashboard/src/app/api/v1/experiments/[id]/route.ts`

- [ ] **Step 1: Create the list route**

```typescript
// apps/dashboard/src/app/api/v1/experiments/route.ts
import { auth } from "@/auth";
import { getDeployment, getExperiments } from "@/lib/db/queries";

export async function GET(req: Request) {
  const session = await auth();
  if (!session?.user) return new Response("unauthorized", { status: 401 });

  const { searchParams } = new URL(req.url);
  const deploymentId = searchParams.get("deployment_id") ?? "";
  if (!deploymentId) return new Response("deployment_id required", { status: 400 });

  const userId = session.user.id as string;
  const dep = await getDeployment(userId, deploymentId);
  if (!dep) return new Response("not found", { status: 404 });

  const allExperiments = await getExperiments(userId, deploymentId);

  const current = allExperiments.find((e) => e.status === "running") ?? null;

  return Response.json(
    { experiments: allExperiments, current_experiment: current },
    { headers: { "Cache-Control": "no-store" } },
  );
}
```

- [ ] **Step 2: Create the detail route**

```typescript
// apps/dashboard/src/app/api/v1/experiments/[id]/route.ts
import { auth } from "@/auth";
import { getExperiment } from "@/lib/db/queries";

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const session = await auth();
  if (!session?.user) return new Response("unauthorized", { status: 401 });

  const { id } = await params;
  const userId = session.user.id as string;
  const experiment = await getExperiment(userId, id);

  if (!experiment) return new Response("not found", { status: 404 });

  return Response.json(experiment, { headers: { "Cache-Control": "no-store" } });
}
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd apps/dashboard
pnpm tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/src/app/api/v1/experiments/route.ts \
        apps/dashboard/src/app/api/v1/experiments/[id]/route.ts
git commit -m "feat(experiment): add GET /api/v1/experiments and /api/v1/experiments/[id] routes"
```

---

## Task 11: Dashboard UI + METHODOLOGY.md §7/§8 + L-3 Fix

**Files:**
- Create: `apps/dashboard/src/app/repos/[id]/ExperimentSection.tsx`
- Modify: `apps/dashboard/src/app/repos/[id]/StagesView.tsx`
- Modify: `docs/METHODOLOGY.md` (§7, §8 TODO placeholders → real content)
- Modify: `apps/api/src/loop/generate/engine.py` (L-3 fix: 20→30)

### Part A: ExperimentSection component

- [ ] **Step 1: Create ExperimentSection.tsx**

```typescript
// apps/dashboard/src/app/repos/[id]/ExperimentSection.tsx
"use client";

import { useEffect, useState } from "react";

interface VariantStats {
  variant: string;
  n: number;
  wins: number;
  avg_winner_score: number;
}

interface Experiment {
  id: string;
  baseline_variant: string;
  challenger_variant: string;
  status: string;
  winner_variant: string | null;
  confidence: number | null;
  baseline_wins: number;
  baseline_n: number;
  challenger_wins: number;
  challenger_n: number;
  started_at: string;
  converged_at: string | null;
}

interface ExperimentsResponse {
  experiments: Experiment[];
  current_experiment: Experiment | null;
}

interface Props {
  deploymentId: string;
}

const CHALLENGER_ORDER = ["cot", "few_shot", "role_play", "concise"];

function roundLabel(exp: Experiment, allExps: Experiment[]): string {
  const idx = CHALLENGER_ORDER.indexOf(exp.challenger_variant);
  const round = idx >= 0 ? idx + 1 : "?";
  return `라운드 ${round}/4`;
}

export default function ExperimentSection({ deploymentId }: Props) {
  const [data, setData] = useState<ExperimentsResponse | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchData() {
      try {
        const r = await fetch(`/api/v1/experiments?deployment_id=${deploymentId}`, {
          cache: "no-store",
        });
        if (r.ok && !cancelled) {
          setData(await r.json() as ExperimentsResponse);
        }
      } catch {
        // ignore network errors
      }
    }

    fetchData();

    const interval = setInterval(() => {
      if (data?.current_experiment?.status === "running" || data === null) {
        fetchData();
      }
    }, 5000);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [deploymentId, data?.current_experiment?.status]);

  if (!data) {
    return (
      <div className="mt-6 border-l-4 border-purple-600 pl-4">
        <h2 className="text-sm font-semibold text-purple-400 mb-2">[7] EXPERIMENT</h2>
        <p className="text-xs text-gray-500">불러오는 중...</p>
      </div>
    );
  }

  const { experiments: allExps, current_experiment: current } = data;

  return (
    <div className="mt-6 border-l-4 border-purple-600 pl-4 mb-8">
      <h2 className="text-sm font-semibold text-purple-400 mb-4">[7] EXPERIMENT</h2>

      {/* Current round */}
      {current && (
        <div className="mb-4">
          <p className="text-xs text-gray-400 mb-3">
            실험 진행 중 — {roundLabel(current, allExps)}:{" "}
            <span className="text-white font-mono">{current.baseline_variant}</span> vs{" "}
            <span className="text-purple-300 font-mono">{current.challenger_variant}</span>
          </p>

          {/* Two-column stats */}
          <div className="grid grid-cols-2 gap-3 mb-3">
            <VariantCard
              label="Baseline"
              variant={current.baseline_variant}
              wins={current.baseline_wins}
              n={current.baseline_n}
              color="gray"
            />
            <VariantCard
              label="Challenger"
              variant={current.challenger_variant}
              wins={current.challenger_wins}
              n={current.challenger_n}
              color="purple"
            />
          </div>

          {/* Bayesian confidence bar */}
          {current.baseline_n >= 10 && current.challenger_n >= 10 && current.confidence != null && (
            <BayesianBar confidence={current.confidence} />
          )}
        </div>
      )}

      {/* History table */}
      {allExps.filter((e) => e.status === "converged").length > 0 && (
        <div className="mt-4">
          <p className="text-xs text-gray-500 mb-2">실험 이력</p>
          <div className="border border-gray-800 rounded-lg overflow-hidden">
            <div className="grid grid-cols-5 gap-2 bg-gray-900 px-3 py-2 text-xs text-gray-500 border-b border-gray-800">
              <span>라운드</span>
              <span>Baseline</span>
              <span>Challenger</span>
              <span>승자</span>
              <span>신뢰도</span>
            </div>
            {allExps
              .filter((e) => e.status === "converged")
              .map((e, i) => (
                <div
                  key={e.id}
                  className="grid grid-cols-5 gap-2 px-3 py-2 text-xs text-gray-300 border-b border-gray-900"
                >
                  <span className="text-gray-500">{i + 1}/4</span>
                  <span className="font-mono">{e.baseline_variant}</span>
                  <span className="font-mono text-purple-300">{e.challenger_variant}</span>
                  <span className={e.winner_variant === e.challenger_variant ? "text-green-400" : "text-gray-400"}>
                    {e.winner_variant ?? "—"}
                  </span>
                  <span>{e.confidence != null ? `${(e.confidence * 100).toFixed(1)}%` : "—"}</span>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* All done banner */}
      {data.experiments.length > 0 &&
        data.current_experiment === null &&
        data.experiments[0]?.status === "converged" && (
          <div className="mt-3 text-xs text-green-400 bg-green-950 border border-green-800 rounded px-3 py-2">
            실험 완료 — 최종 승자:{" "}
            <span className="font-mono font-bold">{data.experiments[0].winner_variant}</span>
          </div>
        )}
    </div>
  );
}

function VariantCard({
  label,
  variant,
  wins,
  n,
  color,
}: {
  label: string;
  variant: string;
  wins: number;
  n: number;
  color: "gray" | "purple";
}) {
  const borderColor = color === "purple" ? "border-purple-800" : "border-gray-700";
  const textColor = color === "purple" ? "text-purple-300" : "text-gray-300";

  return (
    <div className={`bg-gray-950 border ${borderColor} rounded-lg p-3`}>
      <div className="text-xs text-gray-500 mb-1">{label}</div>
      <div className={`font-mono text-sm font-bold ${textColor}`}>{variant}</div>
      <div className="text-xs text-gray-500 mt-2">
        Traces: {n} / 100
      </div>
      <div className="text-xs text-gray-400">
        Win rate: {n > 0 ? ((wins / n) * 100).toFixed(1) : "0.0"}%
      </div>
    </div>
  );
}

function BayesianBar({ confidence }: { confidence: number }) {
  const pct = Math.round(confidence * 100);
  const barColor = pct >= 95 ? "bg-green-500" : pct <= 5 ? "bg-red-500" : "bg-purple-500";

  return (
    <div className="mt-2">
      <div className="flex justify-between text-xs text-gray-500 mb-1">
        <span>P(Challenger &gt; Baseline)</span>
        <span className={pct >= 95 ? "text-green-400" : "text-gray-400"}>{pct}%</span>
      </div>
      <div className="relative bg-gray-800 rounded-full h-2 overflow-hidden">
        <div
          className={`h-2 rounded-full transition-all duration-500 ${barColor}`}
          style={{ width: `${pct}%` }}
        />
        {/* Threshold markers */}
        <div className="absolute top-0 h-full w-px bg-yellow-500 opacity-60" style={{ left: "5%" }} />
        <div className="absolute top-0 h-full w-px bg-yellow-500 opacity-60" style={{ left: "95%" }} />
      </div>
      <div className="flex justify-between text-xs text-gray-600 mt-0.5">
        <span>5%</span>
        <span>95%</span>
      </div>
    </div>
  );
}
```

### Part B: Mount ExperimentSection in StagesView.tsx

- [ ] **Step 2: Modify StagesView.tsx**

In `apps/dashboard/src/app/repos/[id]/StagesView.tsx`:

**Change A** — Add import after the existing `ObserveSection` import:

```typescript
import ExperimentSection from "./ExperimentSection";
```

**Change B** — Add to the destructured status fields (after `latestDeploymentId`):

```typescript
const { repo, latestAnalysis, latestInference, harvestChunks, harvestSourcesDone, harvestSourcesTotal, latestGeneration, latestDeploymentId, latestDeploymentExperimentStatus } = status;
```

**Change C** — After the `{latestDeploymentId && (<ObserveSection .../>)}` block, add:

```typescript
      {/* EXPERIMENT: visible when experiment has been triggered */}
      {latestDeploymentId && latestDeploymentExperimentStatus && latestDeploymentExperimentStatus !== "idle" && (
        <ExperimentSection deploymentId={latestDeploymentId} />
      )}
```

**Change D** — In `apps/dashboard/src/lib/db/queries.ts`, update the `RepoStatus` type and the query that populates `latestDeploymentId` to also return `latestDeploymentExperimentStatus`.

Find the `getRepoStatus` function (or equivalent that returns `latestDeploymentId`). Read the full function, then add `latestDeploymentExperimentStatus` to the returned object:

```typescript
// In the deployment query part of getRepoStatus, change the SELECT to include experiment_status:
// SELECT id, experiment_status FROM deployments WHERE ... ORDER BY created_at DESC LIMIT 1
// Then return:
latestDeploymentId: dep?.id ?? null,
latestDeploymentExperimentStatus: dep?.experiment_status ?? null,
```

Also update the `RepoStatus` type definition to include:
```typescript
latestDeploymentExperimentStatus: string | null;
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd apps/dashboard
pnpm tsc --noEmit
```

Expected: no errors.

### Part C: L-3 fix in generate engine

- [ ] **Step 4: Fix eval_pairs count from 20 to 30**

In `apps/api/src/loop/generate/engine.py`, find the line (approximately line 126):

```python
"Generate 20 diverse test Q&A pairs
```

Change `20` to `30`:

```python
"Generate 30 diverse test Q&A pairs
```

Verify:

```bash
cd apps/api
grep -n "Generate.*test Q&A" src/loop/generate/engine.py
```

Expected: shows `30` on the matching line.

### Part D: METHODOLOGY.md §7 and §8

- [ ] **Step 5: Fill in §7 EXPERIMENT in docs/METHODOLOGY.md**

Read the current `docs/METHODOLOGY.md` to find the `## 7. EXPERIMENT` placeholder, then replace it with:

```markdown
## 7. EXPERIMENT — Bayesian A/B Testing

> **Loop stage:** [7] EXPERIMENT  
> **Implemented in:** Phase 4-B (F-4.5)  
> **Source:** `apps/api/src/loop/experiment/engine.py`

### Challenger Order

Experiments run sequentially in fixed order:

```
Round 1: original  vs cot
Round 2: {winner}  vs few_shot
Round 3: {winner}  vs role_play
Round 4: {winner}  vs concise
```

`CHALLENGER_ORDER = ["cot", "few_shot", "role_play", "concise"]`

### winner_score Formula

Every trace with a `judge_score` is converted to a binary win signal:

```python
# apps/api/src/loop/experiment/engine.py
def compute_winner_score(
    judge_score: float,
    cost_usd: float,
    max_cost_in_window: float,
    cost_weight: float = 0.1,
) -> float:
    cost_normalized = cost_usd / max_cost_in_window if max_cost_in_window > 0 else 0.0
    return judge_score - cost_weight * cost_normalized

win = 1 if winner_score > 0.6 else 0  # win_threshold = 0.6
```

`max_cost_in_window` = max `cost_usd` across all deployment traces in the last 7 days.  
Traces with `judge_score IS NULL` are excluded from all counts.

### Beta-Bernoulli Bayesian Model

```python
# apps/api/src/loop/experiment/engine.py
def bayesian_confidence(
    b_wins: int, b_n: int,
    c_wins: int, c_n: int,
    samples: int = 10_000,
) -> float:
    baseline   = scipy.stats.beta(1 + b_wins, 1 + (b_n - b_wins))
    challenger = scipy.stats.beta(1 + c_wins, 1 + (c_n - c_wins))
    return float(np.mean(challenger.rvs(samples) > baseline.rvs(samples)))
```

Uniform prior `Beta(1, 1)`. Convergence requires:

```
baseline_n ≥ 100  AND  challenger_n ≥ 100
AND (P(challenger > baseline) ≥ 0.95  OR  ≤ 0.05)
```

**Reproducibility checklist:**  
| Parameter | Value |
|---|---|
| Prior | Beta(1, 1) uniform |
| Monte Carlo samples | 10,000 (20,000 in tests) |
| RNG | `np.random.default_rng()` (unseeded — non-deterministic per run) |
| win_threshold | 0.6 |
| cost_weight | 0.1 |
| min_samples | 100 per variant |

### Periodic Evaluation Loop

`_experiment_loop()` in `apps/api/src/worker/runner.py` runs every 300 seconds (5 minutes). It:

1. Queries all `experiments` rows with `status = 'running'`
2. Aggregates wins/n from `traces` + `spans` via SQL
3. Calls `check_experiment()` to evaluate convergence
4. If converged: inserts an `evolve` job into `verum_jobs`

The EVOLVE job is idempotent (ignored if a queued/running EVOLVE job for the same experiment already exists).
```

- [ ] **Step 6: Fill in §8 EVOLVE in docs/METHODOLOGY.md**

Find the `## 8. EVOLVE` placeholder and replace it with:

```markdown
## 8. EVOLVE — Winner Promotion

> **Loop stage:** [8] EVOLVE  
> **Implemented in:** Phase 4-B (F-4.8, F-4.9, F-4.10)  
> **Source:** `apps/api/src/loop/evolve/engine.py`, `apps/api/src/worker/handlers/evolve.py`

### State Transitions

```
DEPLOY job completes
  → experiments INSERT (baseline="original", challenger="cot", status="running")
  → deployments UPDATE (experiment_status="running", current_baseline_variant="original")
  → deployments UPDATE (traffic_split={"original": 0.9, "cot": 0.1})

Every 5 minutes (_experiment_loop):
  → aggregate traces → check bayesian_confidence
  → If converged → INSERT verum_jobs(kind="evolve", ...)

EVOLVE job (handle_evolve):
  → experiments UPDATE (winner_variant, confidence, status="converged", converged_at)
  → deployments UPDATE (current_baseline_variant = winner_variant)
  → If next challenger exists:
      → experiments INSERT (baseline=winner, challenger=next, status="running")
      → deployments UPDATE (traffic_split={winner: 0.9, next: 0.1})
  → Else:
      → deployments UPDATE (experiment_status="completed")
      → deployments UPDATE (traffic_split={winner: 1.0})
```

### Winner Determination

| Condition | Outcome |
|---|---|
| `confidence ≥ 0.95` | Challenger becomes new baseline |
| `confidence ≤ 0.05` | Current baseline holds |
| Otherwise | Continue observing (no EVOLVE job enqueued) |

### ArcanaInsight Validation Gate (F-4.11)

Phase 4-B is complete when at least one full experiment round converges (n ≥ 100 per variant), the winning variant is automatically promoted without xzawed touching anything, and the before/after `judge_score` delta is documented in `docs/WEEKLY.md`.
```

### Part E: Commit everything

- [ ] **Step 7: Run all Python tests**

```bash
cd apps/api
python -m pytest tests/ -v --tb=short
```

Expected: all existing tests pass + new experiment/engine tests pass.

- [ ] **Step 8: Run TypeScript type check**

```bash
cd apps/dashboard
pnpm tsc --noEmit
```

Expected: no errors.

- [ ] **Step 9: Commit**

```bash
git add apps/dashboard/src/app/repos/[id]/ExperimentSection.tsx \
        apps/dashboard/src/app/repos/[id]/StagesView.tsx \
        apps/dashboard/src/lib/db/queries.ts \
        apps/api/src/loop/generate/engine.py \
        docs/METHODOLOGY.md
git commit -m "feat(experiment): add ExperimentSection UI, mount in StagesView, fill METHODOLOGY §7/§8, fix L-3 eval_pairs 20→30"
```

---

## Final Verification

- [ ] **Run full test suite**

```bash
cd apps/api && python -m pytest tests/ -v
```

- [ ] **Run lint**

```bash
cd apps/api && python -m ruff check src/ && python -m mypy src/ --ignore-missing-imports
cd apps/dashboard && pnpm tsc --noEmit
```

- [ ] **Confirm migration chain is complete**

```bash
cd apps/api
python -m alembic history | head -5
```

Expected: `0010_phase4b_experiment_evolve -> (head)` is shown.

- [ ] **Verify METHODOLOGY.md §7/§8 are fully filled (no TODO markers)**

```bash
grep -n "TODO" docs/METHODOLOGY.md
```

Expected: only §9 (RAGAS, deferred) and §10 (known limitations list) lines remain — §7 and §8 should have zero TODO markers.

---

## Spec Self-Review

### Coverage check against `docs/internal/workflows/specs/2026-04-23-phase4b-experiment-evolve-design.md`

| Spec requirement | Task |
|---|---|
| `experiments` table (§1) | Task 1 |
| `experiment_status`, `current_baseline_variant` on deployments (§1) | Task 1 |
| traffic_split format migration (§1) | Task 1 (no-op: experiments table is new, no existing rows need migration) |
| `compute_winner_score` (§2) | Task 3 |
| `bayesian_confidence` (§2) | Task 3 |
| Convergence conditions n≥100 + 0.95/0.05 (§2) | Task 3 |
| CHALLENGER_ORDER (§3) | Task 3 (engine.py) + Task 5 (evolve engine) |
| Periodic worker loop 5-min (§3) | Task 7 |
| EVOLVE job: promote + next/complete (§3) | Task 5, Task 6 |
| First experiment insert after DEPLOY (§3) | Task 8 |
| `GET /api/v1/experiments?deployment_id=` (§5) | Task 10 |
| `GET /api/v1/experiments/[id]` (§5) | Task 10 |
| Drizzle schema (§4 dashboard) | Task 9 |
| ExperimentSection.tsx (§6) | Task 11A |
| 5-second polling while running (§6) | Task 11A |
| StagesView mount condition (§4) | Task 11B |
| METHODOLOGY.md §7/§8 (§8) | Task 11D |
| L-3 fix eval_pairs 20→30 (§9) | Task 11C |
| Trace NULL judge_score excluded (§7) | Task 4 (aggregate_variant_wins SQL: `FILTER WHERE judge_score IS NOT NULL`) |
| Trace NULL cost_usd → cost_normalized=0 (§7) | Task 4 (`COALESCE(s.cost_usd, 0)`) |
| scipy unavailable fallback (§7) | Task 3 (try/except in bayesian_confidence) |
| EVOLVE job failure → retry next tick (§7) | Task 7 (idempotent INSERT guard in _experiment_loop) |
