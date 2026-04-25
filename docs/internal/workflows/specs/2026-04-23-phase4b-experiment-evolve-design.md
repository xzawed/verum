---
type: spec
phase: 4-B
feature: EXPERIMENT + EVOLVE
status: approved
created: 2026-04-23
loop-stages: [7, 8]
roadmap-ids: [F-4.5, F-4.8, F-4.9, F-4.10]
---

# Phase 4-B: EXPERIMENT + EVOLVE — Design Spec

> **Loop stages:** [7] EXPERIMENT + [8] EVOLVE
> **Depends on:** Phase 4-A (OBSERVE, traces with judge_score + cost_usd)
> **Feeds into:** Phase 5 (ArcanaInsight auto-evolution case study, F-5.7)

## Goal

Close the Verum loop completely. After a deployment is created, the system automatically runs sequential pairwise A/B experiments across the 5 prompt variants, selects winners via Bayesian inference, and promotes the best-performing variant to 100% traffic — with no manual intervention from xzawed.

**Phase 4 completion gate (F-4.11):** ArcanaInsight's prompt is auto-improved at least once with a measurable metric gain, with no manual intervention.

---

## Key Decisions

| Decision | Choice | Rationale |
|---|---|---|
| A/B structure | Sequential pairwise | Simpler Bayesian model; compatible with current `traffic_split` schema; multi-variant deferred to Phase 5 |
| Scoring metric | `winner_score = judge_score − 0.1 × cost_normalized` | Judge score available for every trace; cost penalty surfaces efficiency; RAGAS addable later |
| Experiment trigger | Periodic worker loop (5-minute interval) | Achieves "no manual intervention" completion gate; natural fit for existing asyncio worker |

---

## 1. Data Model

### Migration `0010_phase4b_experiment_evolve.py`

#### New table: `experiments`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `deployment_id` | UUID FK → deployments | `ON DELETE CASCADE` |
| `baseline_variant` | TEXT | e.g. `"original"` |
| `challenger_variant` | TEXT | e.g. `"cot"` |
| `status` | TEXT | `running` / `converged` / `abandoned` |
| `winner_variant` | TEXT NULL | Filled on convergence |
| `confidence` | FLOAT NULL | Final Bayesian P(challenger > baseline) or 1-P if baseline wins |
| `baseline_wins` | INT DEFAULT 0 | Traces where baseline winner_score > win_threshold |
| `baseline_n` | INT DEFAULT 0 | Total baseline traces |
| `challenger_wins` | INT DEFAULT 0 | |
| `challenger_n` | INT DEFAULT 0 | |
| `win_threshold` | FLOAT DEFAULT 0.6 | winner_score threshold for binary "win" |
| `cost_weight` | FLOAT DEFAULT 0.1 | Cost penalty weight in winner_score formula |
| `started_at` | TIMESTAMPTZ | |
| `converged_at` | TIMESTAMPTZ NULL | |

##### New columns on `deployments`

| Column | Type | Default | Notes |
|---|---|---|---|
| `experiment_status` | TEXT | `'idle'` | `idle` / `running` / `completed` |
| `current_baseline_variant` | TEXT | `'original'` | Updated after each round |

#### `traffic_split` format change

Current format (Phase 3): `{"baseline": 0.9, "variant": 0.1}` — generic keys.

New format (Phase 4-B): `{"original": 0.9, "cot": 0.1}` — specific variant type names as keys.

Migration `0010` includes a one-time data migration:
```sql
UPDATE deployments
SET traffic_split = jsonb_build_object(
    current_baseline_variant, (traffic_split->>'baseline')::float,
    -- challenger variant inferred from current experiment row
    (SELECT challenger_variant FROM experiments
     WHERE deployment_id = deployments.id
     ORDER BY started_at DESC LIMIT 1),
    (traffic_split->>'variant')::float
)
WHERE traffic_split ? 'baseline';
```
Deployments with no experiment row keep their existing traffic_split unchanged.

---

## 2. Scoring Algorithm

### winner_score formula

```python
def compute_winner_score(
    judge_score: float,
    cost_usd: float,
    max_cost_in_window: float,
    cost_weight: float = 0.1,
) -> float:
    cost_normalized = cost_usd / max_cost_in_window if max_cost_in_window > 0 else 0.0
    return judge_score - cost_weight * cost_normalized
```

`max_cost_in_window` = max `cost_usd` across all traces for the deployment in the last 7 days.

### Beta-Bernoulli Bayesian model

Convert winner_score to binary using `win_threshold = 0.6`:

```python
win = 1 if winner_score > win_threshold else 0
```

Posterior for each variant: `Beta(1 + wins, 1 + losses)` (uniform prior).

### Convergence check

```python
def bayesian_confidence(
    b_wins: int, b_n: int,
    c_wins: int, c_n: int,
    samples: int = 10_000,
) -> float:
    baseline   = scipy.stats.beta(1 + b_wins, 1 + (b_n - b_wins))
    challenger = scipy.stats.beta(1 + c_wins, 1 + (c_n - c_wins))
    return float(np.mean(challenger.rvs(samples) > baseline.rvs(samples)))
```

**Convergence conditions (both required):**

```
baseline_n ≥ 100 AND challenger_n ≥ 100          (minimum sample gate)
AND (
  P(challenger > baseline) ≥ 0.95                (challenger wins)
  OR P(challenger > baseline) ≤ 0.05             (baseline holds)
)
```

**Winner determination:**
- `conf ≥ 0.95` → challenger becomes new baseline
- `conf ≤ 0.05` → current baseline holds
- Otherwise → continue observing

---

## 3. Experiment Lifecycle

### Challenger order (constant)

```python
CHALLENGER_ORDER = ["cot", "few_shot", "role_play", "concise"]
```

Round 1: `original` vs `cot`
Round 2: `{round-1 winner}` vs `few_shot`
Round 3: `{round-2 winner}` vs `role_play`
Round 4: `{round-3 winner}` vs `concise`

After round 4: `deployment.experiment_status = "completed"`. Final winner is at 100% traffic.

### State transitions

```
DEPLOY job completes
  → INSERT experiments(baseline="original", challenger="cot", status="running")
  → UPDATE deployments SET experiment_status="running", current_baseline_variant="original"
  → UPDATE deployments SET traffic_split={"original": 0.9, "cot": 0.1}

Every 5 minutes (worker loop):
  → Query all deployments WHERE experiment_status="running"
  → For each: aggregate traces, compute bayesian_confidence
  → If converged: enqueue verum_jobs(kind="evolve", payload={experiment_id, winner_variant})

EVOLVE job:
  → UPDATE experiments SET winner_variant, confidence, status="converged", converged_at
  → UPDATE deployments SET current_baseline_variant = winner_variant
  → If next challenger exists:
      → INSERT experiments(baseline=winner, challenger=next, status="running")
      → UPDATE deployments SET traffic_split={winner: 0.9, next: 0.1}
  → Else:
      → UPDATE deployments SET experiment_status="completed"
      → UPDATE deployments SET traffic_split={winner: 1.0}
```

---

## 4. New Files

### Python Worker

| File | Purpose |
|---|---|
| `apps/api/src/loop/experiment/engine.py` | `compute_winner_score()`, `bayesian_confidence()`, `check_experiment()` |
| `apps/api/src/loop/experiment/models.py` | `ExperimentResult`, `VariantStats` Pydantic models |
| `apps/api/src/loop/experiment/repository.py` | `get_running_experiment()`, `update_experiment_stats()`, `insert_experiment()` |
| `apps/api/src/loop/evolve/engine.py` | `promote_winner()`, `start_next_challenger()`, `complete_deployment()` |
| `apps/api/src/loop/evolve/repository.py` | `update_deployment_baseline()`, `update_traffic_split()` |
| `apps/api/src/worker/handlers/evolve.py` | `handle_evolve()` — EVOLVE job handler |
| `apps/api/alembic/versions/0010_phase4b_experiment_evolve.py` | Migration |

### Modified Python files

| File | Change |
|---|---|
| `apps/api/src/worker/runner.py` | Add `_experiment_loop()` background task started from `main()` at boot + register `evolve` handler in `_HANDLERS` |
| `apps/api/src/worker/handlers/deploy.py` | After deploy completes: insert first experiment row |
| `apps/api/src/loop/generate/engine.py` | Fix L-3: change eval_pairs request from 20 → 30 |

### Next.js Dashboard

| File | Purpose |
|---|---|
| `apps/dashboard/src/app/api/v1/experiments/route.ts` | `GET` list for a deployment |
| `apps/dashboard/src/app/api/v1/experiments/[id]/route.ts` | `GET` detail + Bayesian stats |
| `apps/dashboard/src/lib/db/schema.ts` | Add `experiments` table + new `deployments` columns |
| `apps/dashboard/src/lib/db/queries.ts` | `getExperiments(userId, deploymentId)`, `getExperiment(userId, id)` |
| `apps/dashboard/src/app/repos/[id]/ExperimentSection.tsx` | Experiment UI component |

### Modified Next.js files

| File | Change |
|---|---|
| `apps/dashboard/src/app/repos/[id]/StagesView.tsx` | Mount `ExperimentSection` when `experiment_status !== 'idle'` |

---

## 5. API Endpoints

### Browser-facing (Auth.js session)

#### `GET /api/v1/experiments?deployment_id=<uuid>`

Returns all experiments for a deployment, ordered by `started_at DESC`.

```json
{
  "experiments": [
    {
      "id": "uuid",
      "baseline_variant": "original",
      "challenger_variant": "cot",
      "status": "converged",
      "winner_variant": "cot",
      "confidence": 0.973,
      "baseline_n": 312,
      "challenger_n": 104,
      "started_at": "2026-04-23T10:00:00Z",
      "converged_at": "2026-04-25T14:22:00Z"
    }
  ],
  "current_experiment": { ... } | null
}
```

#### `GET /api/v1/experiments/[id]`

Full detail including live Bayesian stats for running experiments.

---

## 6. Dashboard UI — ExperimentSection.tsx

Mounted in `StagesView.tsx` when `latestDeployment.experiment_status !== 'idle'`.

**Content:**

- **Status header**: "실험 진행 중 — 라운드 2/4: baseline vs few_shot"
- **Two-column stats card** (baseline | challenger):
  - Variant name + type badge
  - Traces: n / 100 (progress toward minimum)
  - Avg winner_score (judge − cost component)
  - Win rate (wins / n)
- **Bayesian confidence bar**: animated 0–100%, threshold line at 95%
- **Convergence banner** (when status = `converged`): "CoT 승 (신뢰도 97.3%) — 다음: few_shot 도전 중"
- **Experiment history table**: past rounds with baseline / challenger / winner / confidence / duration

Data fetching:
- `GET /api/v1/experiments?deployment_id=...` on mount
- Polls every 5 seconds while `status = "running"`

---

## 7. Error Handling

| Scenario | Behavior |
|---|---|
| Trace has no `judge_score` (NULL) | Excluded from Bayesian computation — does not count toward n |
| Trace has no `cost_usd` (unknown model) | `cost_normalized = 0` — no cost penalty applied |
| `scipy` unavailable | `bayesian_confidence` falls back to raw win-rate ratio; logged as warning |
| EVOLVE job fails | Experiment stays `running`; retried on next 5-min loop tick |
| All variants abandoned (no convergence after 30 days) | `experiment_status = "abandoned"` (future Phase 5 policy) |

---

## 8. METHODOLOGY.md Update

§7 (EXPERIMENT) and §8 (EVOLVE) in `docs/METHODOLOGY.md` are filled in as part of this phase's implementation PR, per the METHODOLOGY.md update rule.

---

## 9. Known Limitations (Phase 4-B scope)

- **L-3 fix included**: eval_pairs count changed from 20 → 30 in `engine.py`
- **L-1, L-2 deferred**: RAG constraint mismatches not fixed in this phase
- **L-5 deferred**: Judge temperature still not specified
- **RAGAS (F-4.6)**: not included — addable to winner_score formula in follow-up PR
- **Abandonment policy**: 30-day timeout is future work; no implementation in this phase
- **Multi-variant**: deferred to Phase 5

---

## 10. ArcanaInsight Validation Gate

Phase 4-B is complete when:

1. At least one full experiment round converges (confidence ≥ 0.95, n ≥ 100 per variant)
2. The winning variant is automatically promoted (traffic_split updates without xzawed touching anything)
3. Dashboard shows experiment history with at least one completed round
4. xzawed documents the before/after judge_score delta in `docs/WEEKLY.md`
