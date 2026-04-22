# Design: Phase 0 / Phase 1 / Phase 3 Completion

**Date:** 2026-04-22
**Author:** xzawed
**Status:** Approved
**Scope:** F-0.7, F-1.4, F-1.8, F-3.4 through F-3.10

---

## 1. Overview

This spec covers all remaining deliverables for Phase 0, Phase 1, and Phase 3 of the Verum roadmap.
Work is grouped into 6 batches executed in Phase order, with independent items parallelized within each batch.

```
Batch 0   : F-0.7  — CI fix
Batch 1   : F-1.4 (ArcanaInsight verify) + F-1.8 (REST endpoints) — parallel
Batch 2   : F-3.4 (metric profile) + F-3.5 (GENERATE API + UI) — parallel
Batch 3   : F-3.6 + F-3.7 (DEPLOY engine + API)
Batch 4   : F-3.8 (Python SDK) + F-3.9 (TypeScript SDK) — parallel
Batch 5   : F-3.10 (ArcanaInsight integration) — Phase 3 gate
```

---

## 2. Batch 0 — Phase 0 · F-0.7: CI Fix

**File:** `.github/workflows/ci.yml`

Two changes only:

1. Fix pip install path in `lint-python` and `test-api` jobs:
   ```diff
   - run: pip install "apps/api[dev]"
   + run: pip install -e "./apps/api[dev]"
   ```

2. Add `pylint` step to `lint-python` job after `bandit`:
   ```yaml
   - name: pylint
     run: pylint apps/api/src --fail-under=8.0
   ```

**Completion:** CI passes on push to `main`.

---

## 3. Batch 1 — Phase 1

### F-1.4: ArcanaInsight ANALYZE Validation

Run the existing CLI against the live ArcanaInsight repo and capture results:

```bash
python -m src.loop.analyze.cli \
  --repo https://github.com/xzawed/ArcanaInsight \
  --branch main \
  > /tmp/arcana-result.json
```

Validation assertions:
- `call_sites` count ≥ 1
- At least one entry has `sdk = "grok"`
- Each entry has non-null `file_path` and `line`

Results documented in `docs/WEEKLY.md`. ROADMAP F-1.4 updated to ✅.

### F-1.8: REST Endpoints

New Next.js API routes under `apps/dashboard/src/app/api/v1/`:

| Method | Route | Action |
|--------|-------|--------|
| POST | `/api/v1/analyze` | Enqueue `analyze` job in `verum_jobs`, return `{ job_id }` |
| GET | `/api/v1/analyze/[id]` | Return analysis status + `call_sites` from DB via Drizzle |
| POST | `/api/v1/infer` | Enqueue `infer` job, return `{ job_id }` |
| GET | `/api/v1/infer/[id]` | Return inference status + `ServiceInference` fields |

Implementation pattern: identical to existing `/api/repos/[id]/status/route.ts`.
Auth: session required (Auth.js). All routes check `session.user.id` owns the resource.

---

## 4. Batch 2 — Phase 3 · F-3.4 + F-3.5

### F-3.4: Dashboard Metric Profile Auto-Selection

New file: `apps/api/src/loop/generate/metric_profile.py`

Pure function — no LLM call, no DB:

```python
def select_metric_profile(user_type: str, domain: str) -> MetricProfile:
    ...
```

`MetricProfile` Pydantic model:
```python
class MetricProfile(BaseModel):
    primary_metrics: list[str]   # e.g. ["latency_p95", "user_satisfaction"]
    secondary_metrics: list[str]
    profile_name: str            # e.g. "consumer-divination"
```

Selection table:
| user_type | Primary metrics |
|-----------|----------------|
| `consumer` | latency_p95, user_satisfaction, response_length |
| `developer` | accuracy, latency_p95, cost_per_call |
| `enterprise` | cost_per_call, reliability, throughput |

Domain overrides: `divination/*` adds `response_length` to primary.

`MetricProfile` persisted in `generations.metric_profile` (JSONB column).
Alembic migration adds this column if not present.

### F-3.5: GENERATE API Endpoints + Dashboard Page

**API routes** (`apps/dashboard/src/app/api/v1/generate/`):

| Method | Route | Action |
|--------|-------|--------|
| POST | `/api/v1/generate` | Enqueue `generate` job (payload: `inference_id`), call `create_pending_generation`, return `{ generation_id }` |
| GET | `/api/v1/generate/[id]` | Return generation status, `prompt_variants`, `rag_config`, `eval_pairs`, `metric_profile` |
| PATCH | `/api/v1/generate/[id]/approve` | Set `generations.status = "approved"`, return updated row |

**Dashboard page** `apps/dashboard/src/app/generate/[inference_id]/page.tsx`:
- Poll `GET /api/v1/generate/[id]` every 3 seconds while `status = "pending"` (same pattern as harvest page)
- Display 5 prompt variant cards (tabs by variant_type)
- RAG config summary card
- First 5 eval pairs preview
- Metric profile badges
- [생성 시작] button → `POST /api/v1/generate`
- [승인] button (enabled when `status = "done"`) → `PATCH /approve` → redirect to `/deploy/[generation_id]`

---

## 5. Batch 3 — Phase 3 · F-3.6 + F-3.7: DEPLOY

### F-3.6: DEPLOY Engine

New module: `apps/api/src/loop/deploy/`

```
deploy/
  __init__.py
  models.py       ← Deployment, DeploymentConfig Pydantic models
  engine.py       ← create_canary(), adjust_traffic(), rollback(), get_config()
  repository.py   ← DB CRUD
```

**Pydantic models:**
```python
class DeploymentConfig(BaseModel):
    traffic_split: float = 0.10    # 0.0–1.0, fraction to variant
    rollback_threshold: float = 5.0  # error rate multiplier

class Deployment(BaseModel):
    deployment_id: UUID
    generation_id: UUID
    status: str          # "canary" | "full" | "rolled_back" | "archived"
    traffic_split: dict[str, float]   # {"baseline": 0.9, "variant": 0.1}
    error_count: int
    total_calls: int
    created_at: datetime
    updated_at: datetime
```

**DB schema** (Alembic migration):
```sql
CREATE TABLE deployments (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  generation_id UUID NOT NULL REFERENCES generations(id),
  status        TEXT NOT NULL DEFAULT 'canary',
  traffic_split JSONB NOT NULL DEFAULT '{"baseline": 0.9, "variant": 0.1}',
  error_count   INT NOT NULL DEFAULT 0,
  total_calls   INT NOT NULL DEFAULT 0,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**Auto-rollback logic** (in `engine.py`):
- Triggered when `total_calls >= 100` AND `error_rate > baseline_error_rate * 5`
- `baseline_error_rate` defaults to 0.01 (1%) if no prior data
- On trigger: set `status = "rolled_back"`, `traffic_split = {"baseline": 1.0, "variant": 0.0}`

**SDK config endpoint response** (`VERUM_API_KEY` 헤더 인증, session 불필요):
```json
{
  "deployment_id": "...",
  "status": "canary",
  "traffic_split": 0.10,
  "variant_prompt": "..."
}
```

### F-3.7: DEPLOY API Endpoints + Dashboard Page

**API routes** (`apps/dashboard/src/app/api/v1/deploy/`):

| Method | Route | Action |
|--------|-------|--------|
| POST | `/api/v1/deploy` | Create canary deployment (payload: `generation_id`), enqueue `deploy` worker job |
| GET | `/api/v1/deploy/[id]` | Return deployment status, traffic_split, error_count, total_calls |
| PATCH | `/api/v1/deploy/[id]/traffic` | Adjust traffic split (payload: `{ split: 0.5 }`) |
| POST | `/api/v1/deploy/[id]/rollback` | Immediately rollback to baseline |
| GET | `/api/v1/deploy/[id]/config` | SDK polling endpoint — `VERUM_API_KEY` header 인증, session 불필요, returns variant prompt + split |

**Dashboard page** `apps/dashboard/src/app/deploy/[id]/page.tsx` (id = deployment_id):
- Traffic percentage slider (10% / 50% / 100% presets + custom)
- Error rate counter (`error_count / total_calls`)
- Auto-rollback status badge
- [롤백] button
- [100% 승격] button

Generate 페이지에서 `POST /api/v1/deploy` 호출 후 응답의 `deployment_id`로 이 페이지에 리다이렉트.

**Worker handler** `apps/api/src/worker/handlers/deploy.py`:
- Receives `{ generation_id }`, calls `deploy.engine.create_canary()`
- Persists `Deployment` row, returns `{ deployment_id }`

---

## 6. Batch 4 — Phase 3 · F-3.8 + F-3.9: SDKs

### F-3.8: Python SDK (`packages/sdk-python/`)

**Package structure:**
```
sdk-python/
  src/verum/
    __init__.py      ← re-exports Client
    client.py        ← VerumClient class
    _cache.py        ← DeploymentConfigCache (60s TTL)
    _router.py       ← traffic split routing logic
  pyproject.toml     ← name="verum", version="0.1.0"
  README.md
  tests/
```

**Public API:**
```python
class Client:
    def __init__(
        self,
        api_url: str | None = None,   # fallback: VERUM_API_URL env
        api_key: str | None = None,   # fallback: VERUM_API_KEY env
    ): ...

    async def chat(
        self,
        messages: list[dict],
        *,
        deployment_id: str | None = None,
        provider: str = "openai",     # "openai" | "anthropic" | "grok"
        model: str,
        **kwargs,                     # passed through to underlying SDK
    ) -> dict: ...

    async def retrieve(
        self,
        query: str,
        *,
        collection_name: str,
        top_k: int = 5,
    ) -> list[dict]: ...

    async def feedback(
        self,
        trace_id: str,
        score: int,                   # 1 = positive, -1 = negative
    ) -> None: ...
```

**Routing logic** (`_router.py`):
1. If `deployment_id` is None → pass through, no routing
2. Fetch config from `GET /api/v1/deploy/[deployment_id]/config` (60s TTL cache)
3. If `random.random() < config.traffic_split` → replace `messages[0]["content"]` with `config.variant_prompt`
4. Call underlying LLM SDK directly (no Verum proxy)

**Packaging:** `pip install verum` installable, `httpx` as sole runtime dependency.
**Tests:** ≥ 80% coverage using `respx` to mock HTTP calls.

### F-3.9: TypeScript SDK (`packages/sdk-typescript/`)

**Package structure:**
```
sdk-typescript/
  src/
    index.ts         ← re-exports VerumClient
    client.ts        ← VerumClient class
    cache.ts         ← DeploymentConfigCache (60s TTL)
    router.ts        ← traffic split routing logic
  package.json       ← name="@verum/sdk", version="0.1.0"
  tsconfig.json
  README.md
  tests/
```

**Public API (mirrors Python SDK):**
```typescript
class VerumClient {
  constructor(options?: { apiUrl?: string; apiKey?: string });

  chat(params: {
    messages: ChatMessage[];
    deploymentId?: string;
    provider?: "openai" | "anthropic" | "grok";
    model: string;
    [key: string]: unknown;
  }): Promise<unknown>;

  retrieve(params: {
    query: string;
    collectionName: string;
    topK?: number;
  }): Promise<Chunk[]>;

  feedback(params: {
    traceId: string;
    score: 1 | -1;
  }): Promise<void>;
}
```

**Routing logic:** identical to Python SDK — 60s TTL cache, `Math.random() < split` decision.
**Packaging:** `npm install @verum/sdk`, `fetch` API only (no extra dependencies).
**Tests:** Jest, ≥ 80% coverage.

---

## 7. Batch 5 — Phase 3 · F-3.10: ArcanaInsight Integration

**What Verum delivers:**

`examples/arcana-integration/` directory:
```
examples/arcana-integration/
  README.md        ← Step-by-step guide (Korean)
  before.py        ← ArcanaInsight tarot endpoint pattern (pre-Verum)
  after.py         ← Same endpoint using verum.chat() + verum.retrieve()
  .env.example     ← VERUM_API_URL, VERUM_API_KEY, VERUM_DEPLOYMENT_ID
```

**`after.py` canonical pattern:**
```python
import os
import verum

verum_client = verum.Client()

async def tarot_reading(user_message: str) -> str:
    # 1. Retrieve tarot knowledge context
    chunks = await verum_client.retrieve(
        query=user_message,
        collection_name="arcana-tarot-knowledge",
        top_k=5,
    )
    context = "\n".join(c["content"] for c in chunks)

    # 2. Call LLM with Verum routing (10% goes to CoT variant)
    response = await verum_client.chat(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Context:\n{context}\n\n{user_message}"},
        ],
        deployment_id=os.environ["VERUM_DEPLOYMENT_ID"],
        provider="grok",
        model="grok-2-1212",
    )
    return response["choices"][0]["message"]["content"]
```

**What xzawed does manually:**
1. `pip install verum` in ArcanaInsight
2. Copy `after.py` pattern into ArcanaInsight tarot endpoint
3. Set `VERUM_API_URL`, `VERUM_API_KEY`, `VERUM_DEPLOYMENT_ID` env vars
4. Deploy ArcanaInsight
5. Verify 10% canary traffic hitting CoT variant via Verum dashboard
6. Record results in `docs/WEEKLY.md`

**Phase 3 completion gate:** xzawed confirms in `docs/WEEKLY.md` that tarot consultation runs on Verum-generated prompt + RAG retrieval.

---

## 8. Data Flow Summary

```
[GENERATE approved] 
    → POST /api/v1/deploy (create canary)
    → Deployment row (status=canary, split=10%)
    → ArcanaInsight calls verum.chat(deployment_id=X)
        → SDK fetches /api/v1/deploy/X/config (60s cache)
        → 10% → CoT variant prompt
        → 90% → original prompt
        → LLM called directly by SDK
    → Dashboard shows traffic counts
    → xzawed adjusts split via slider
```

---

## 9. Out of Scope

- Phase 4 (OBSERVE/EXPERIMENT/EVOLVE) — separate spec
- Playwright-based JS crawling (deferred to Phase 3 per F-2.6 note)
- Semantic chunking (deferred per F-2.8 note)
- Multi-tenant / team collaboration features
- Payment / billing

---

## 10. Open Questions (Resolved)

| Question | Decision |
|----------|----------|
| SDK LLM proxy vs direct call | Direct call — lower latency; OBSERVE adds telemetry in Phase 4 |
| Traffic split cache TTL | 60 seconds — acceptable staleness vs API overhead |
| Auto-rollback threshold | 5× baseline error rate after 100 calls |
| F-1.8 scope | Expose `/v1/analyze` and `/v1/infer` as Next.js routes; `/v1/harvest` and `/v1/retrieve` also included |
| F-3.10 scope | Verum provides example + guide; xzawed applies to ArcanaInsight manually |

---

_Maintainer: xzawed | Last updated: 2026-04-22_
