---
type: spec
phase: 4-A
feature: OBSERVE
status: approved
created: 2026-04-23
loop-stages: [6]
roadmap-ids: [F-4.1, F-4.2, F-4.3, F-4.4]
---

# Phase 4-A: OBSERVE — Design Spec

> **Loop stage:** [6] OBSERVE
> **Depends on:** Phase 3 (DEPLOY, SDK) fully implemented
> **Feeds into:** Phase 4-B EXPERIMENT (trace data → A/B comparison)

## Goal

Close the observability gap: every `verum.chat()` call in ArcanaInsight produces a
persisted trace with latency, token count, cost, LLM-as-Judge quality score, and
optional user feedback. The dashboard shows 7-day trends per deployment variant.

**ArcanaInsight completion gate (F-4.11 partial):** After integrating `client.record()`,
every tarot reading call appears in the Verum traces table with a judge_score within
60 seconds of the call completing.

---

## 1. Data Model

Four new tables added via Alembic migration `0009_phase4a_observe.py`.

### `model_pricing`

Stores per-model token pricing. Managed via DB — no hardcoding.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `model_name` | TEXT UNIQUE | e.g. `"grok-2-1212"`, `"claude-sonnet-4-6"` |
| `input_per_1m_usd` | NUMERIC(10,6) | Cost per 1M input tokens in USD |
| `output_per_1m_usd` | NUMERIC(10,6) | Cost per 1M output tokens in USD |
| `provider` | TEXT | `"xai"` / `"anthropic"` / `"openai"` |
| `effective_from` | TIMESTAMPTZ | Price valid from this date |

**Initial seed data (included in migration):**

| model_name | input/1M | output/1M | provider |
|---|---|---|---|
| `grok-2-1212` | $2.00 | $10.00 | xai |
| `grok-2-mini` | $0.20 | $0.40 | xai |
| `claude-sonnet-4-6` | $3.00 | $15.00 | anthropic |
| `claude-haiku-4-5` | $0.80 | $4.00 | anthropic |
| `gpt-4o` | $2.50 | $10.00 | openai |
| `gpt-4o-mini` | $0.15 | $0.60 | openai |

### `traces`

One row per `client.record()` call — represents a single LLM call event.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | Returned to caller as `trace_id` |
| `deployment_id` | UUID FK → deployments | Which deployment this trace belongs to |
| `variant` | TEXT | `"baseline"` / `"cot"` / `"few_shot"` / `"role_play"` / `"concise"` |
| `user_feedback` | SMALLINT NULL | `1` (👍) / `-1` (👎) / NULL (no feedback) |
| `judge_score` | FLOAT NULL | 0.0–1.0; filled asynchronously by judge handler |
| `created_at` | TIMESTAMPTZ | |

### `spans`

One row per trace — stores the raw LLM call metrics.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `trace_id` | UUID FK → traces | |
| `model` | TEXT | Exact model name used |
| `input_tokens` | INT | From LLM SDK response |
| `output_tokens` | INT | From LLM SDK response |
| `latency_ms` | INT | Measured by caller |
| `cost_usd` | NUMERIC(10,6) | Calculated: `(input/1M × input_per_1m) + (output/1M × output_per_1m)` |
| `error` | TEXT NULL | Error message if call failed |
| `started_at` | TIMESTAMPTZ | |

### `judge_prompts`

Stores full judge context for auditability and debugging. One row per judged trace.

| Column | Type | Notes |
|---|---|---|
| `trace_id` | UUID PK FK → traces | |
| `prompt_sent` | TEXT | Full prompt sent to Claude |
| `raw_response` | TEXT | Claude's raw JSON response |
| `judged_at` | TIMESTAMPTZ | |

---

## 2. API Endpoints

### SDK-facing (API key auth via `X-Verum-API-Key` header)

#### `POST /api/v1/traces`

Receives a trace from `client.record()`. Saves trace + span, calculates cost, enqueues judge job.

**Request body:**
```json
{
  "deployment_id": "uuid",
  "variant": "cot",
  "model": "grok-2-1212",
  "input_tokens": 512,
  "output_tokens": 284,
  "latency_ms": 980,
  "error": null
}
```

**Response:**
```json
{ "trace_id": "uuid" }
```

**Side effects:**
1. Looks up `model_pricing` by `model` name → calculates `cost_usd`
2. Inserts into `traces` and `spans` in a single transaction
3. Enqueues `verum_jobs` row: `{kind: "judge", payload: {trace_id, deployment_id, variant}}`

If `model` is not found in `model_pricing`, cost is stored as `0.000000` and a warning is logged — never an error.

#### `POST /api/v1/feedback`

Updates `traces.user_feedback`. Already stubbed in SDK; this implements the backend.

**Request body:**
```json
{ "trace_id": "uuid", "score": 1 }
```

`score` must be `1` or `-1`. Returns `204 No Content`.

### Browser-facing (Auth.js session)

#### `GET /api/v1/traces?deployment_id=<uuid>&page=<n>&limit=<n>`

Paginated trace list filtered by deployment. Returns traces joined with their single span.

**Response:**
```json
{
  "traces": [
    {
      "id": "uuid",
      "variant": "cot",
      "latency_ms": 980,
      "cost_usd": "0.003100",
      "judge_score": 0.82,
      "user_feedback": 1,
      "created_at": "2026-04-23T10:00:00Z"
    }
  ],
  "total": 2140,
  "page": 1
}
```

#### `GET /api/v1/traces/[id]`

Full trace detail: trace row + span row + judge_prompts row (if judged).

#### `GET /api/v1/metrics?deployment_id=<uuid>&days=7`

7-day daily aggregation for the chart.

**Response:**
```json
{
  "daily": [
    {
      "date": "2026-04-17",
      "total_cost_usd": 0.42,
      "call_count": 312,
      "p95_latency_ms": 1240,
      "avg_judge_score": 0.74
    }
  ]
}
```

---

## 3. Python SDK — `client.record()`

Added to `packages/sdk-python/src/verum/client.py`.

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

    Call immediately after the LLM SDK returns. The trace_id can be passed
    to feedback() if the user provides a rating.

    Args:
        deployment_id: From client.chat() response["deployment_id"].
        variant: From client.chat() response["variant"].
        model: Exact model string used (e.g. "grok-2-1212").
        input_tokens: From LLM response usage.prompt_tokens.
        output_tokens: From LLM response usage.completion_tokens.
        latency_ms: Wall-clock time from request start to response end.
        error: Error message if the LLM call failed; None on success.

    Returns:
        trace_id string to pass to feedback().
    """
```

**ArcanaInsight integration pattern:**

```python
import time
import verum

client = verum.Client()  # VERUM_API_URL + VERUM_API_KEY from env

routed = await client.chat(
    messages=[{"role": "user", "content": user_query}],
    deployment_id=DEPLOYMENT_ID,
    provider="grok",
    model="grok-2-1212",
)

t0 = time.monotonic()
grok_resp = grok_client.chat.completions.create(
    model="grok-2-1212",
    messages=routed["messages"],
)
latency_ms = int((time.monotonic() - t0) * 1000)

trace_id = await client.record(
    deployment_id=routed["deployment_id"],
    variant=routed["variant"],
    model="grok-2-1212",
    input_tokens=grok_resp.usage.prompt_tokens,
    output_tokens=grok_resp.usage.completion_tokens,
    latency_ms=latency_ms,
)

# When user gives feedback (optional):
await client.feedback(trace_id=trace_id, score=1)
```

---

## 4. Python Worker — `handle_judge`

**File:** `apps/api/src/worker/handlers/judge.py`

**Job kind:** `"judge"`

**Payload:**
```json
{
  "trace_id": "uuid",
  "deployment_id": "uuid",
  "variant": "cot"
}
```

**Algorithm:**

1. Load `trace` row by `trace_id`. If already has `judge_score`, skip (idempotent).
2. Load the `span` row to get the LLM input/output (note: we do not store the actual prompt/response text in spans — see limitation below).
3. Load `deployment` → `generation` → up to 3 `eval_pairs` most representative of the domain (first 3 by `created_at`).
4. Build judge prompt:
   ```
   You are evaluating an AI assistant response for quality.
   Score from 0.0 to 1.0 based on: domain appropriateness,
   completeness, and alignment with the expected answer direction.

   Domain: {domain} | Tone: {tone}
   Reference examples: {eval_pairs[0..2]}

   Respond ONLY with JSON: {"score": 0.0-1.0, "reason": "one sentence"}
   ```
5. Call `claude-sonnet-4-6` with this prompt.
6. Parse JSON response. On parse failure: retry once. If still fails: log warning, leave `judge_score = NULL`, mark job `done`.
7. `UPDATE traces SET judge_score = {score} WHERE id = {trace_id}`
8. `INSERT INTO judge_prompts (trace_id, prompt_sent, raw_response, judged_at)`

**Limitation:** `spans` does not store the actual user query or assistant response text (privacy/cost consideration). The judge prompt uses eval_pairs as domain reference only, not the actual call content. This means judge scores measure "domain alignment" not "exact response correctness." This is intentional for Phase 4-A; storing call content is opt-in and deferred to Phase 5.

**Registration in `runner.py`:**
```python
from apps.api.src.worker.handlers.judge import handle_judge
_HANDLERS = {
    ...
    "judge": handle_judge,
}
```

---

## 5. Dashboard UI

### Page location

OBSERVE is added as a new section within the existing `/repos/[id]` page, consistent with how GENERATE and DEPLOY are surfaced. No new top-level page.

### New files

**`apps/dashboard/src/app/repos/[id]/ObserveSection.tsx`**

Renders when `deployment` exists (Phase 3 complete). Contains:

- **Period selector** — dropdown: "최근 7일" / "최근 30일"
- **Metric cards (4)** — Total cost / P95 latency / Call count / Avg judge score. Each shows value + trend vs previous period.
- **Daily bar chart** — Recharts `BarChart` with 7 bars (one per day). Y-axis: cost in USD. Tooltip shows call count + avg judge score for that day.
- **Trace table** — Columns: Trace ID (truncated) / Variant / Latency / Cost / Judge score / Feedback. Paginated (20 per page). Clicking a row opens `SpanWaterfall`.

**`apps/dashboard/src/components/SpanWaterfall.tsx`**

Slide-over panel (right side, `fixed` positioning). Shows:
- Trace metadata: deployment, variant, created_at
- Single span bar: latency breakdown (just total for Phase 4-A; per-segment breakdown in Phase 5)
- Cost breakdown: input tokens × rate + output tokens × rate = total
- Judge section: score (0–1 progress bar) + reason text from `judge_prompts.raw_response`
- User feedback badge

### Data fetching

`ObserveSection` fetches from:
- `GET /api/v1/metrics?deployment_id=...&days=7` on mount and on period change
- `GET /api/v1/traces?deployment_id=...&page=1` on mount; re-fetches on page change

`SpanWaterfall` fetches `GET /api/v1/traces/[id]` when a row is clicked.

---

## 6. New Files Summary

| File | Type | Purpose |
|---|---|---|
| `apps/api/alembic/versions/0009_phase4a_observe.py` | Migration | 4 new tables + seed pricing data |
| `apps/api/src/loop/observe/models.py` | Python | `TraceRecord`, `SpanRecord` Pydantic models |
| `apps/api/src/loop/observe/repository.py` | Python | `insert_trace()`, `update_judge_score()`, `get_metrics()` |
| `apps/api/src/worker/handlers/judge.py` | Python | `handle_judge` — LLM-as-Judge async handler |
| `apps/dashboard/src/app/api/v1/traces/route.ts` | Next.js | `GET` (list) + `POST` (ingest) |
| `apps/dashboard/src/app/api/v1/traces/[id]/route.ts` | Next.js | `GET` (detail + spans) |
| `apps/dashboard/src/app/api/v1/metrics/route.ts` | Next.js | `GET` (7-day aggregation) |
| `apps/dashboard/src/app/api/v1/feedback/route.ts` | Next.js | `POST` (update user_feedback) |
| `apps/dashboard/src/app/repos/[id]/ObserveSection.tsx` | React | Metrics + chart + trace table |
| `apps/dashboard/src/components/SpanWaterfall.tsx` | React | Slide-over panel: span detail + judge |

**Modified files:**

| File | Change |
|---|---|
| `apps/api/src/worker/runner.py` | Add `"judge": handle_judge` to `_HANDLERS` |
| `packages/sdk-python/src/verum/client.py` | Add `record()` method |
| `apps/dashboard/src/app/repos/[id]/page.tsx` (or `StagesView.tsx`) | Mount `ObserveSection` when deployment exists |

---

## 7. Authentication

| Endpoint | Auth method | Reason |
|---|---|---|
| `POST /api/v1/traces` | `X-Verum-API-Key` header | SDK-to-API, no browser session |
| `POST /api/v1/feedback` | `X-Verum-API-Key` header | SDK-to-API, no browser session |
| `GET /api/v1/traces` | Auth.js session | Browser request |
| `GET /api/v1/traces/[id]` | Auth.js session | Browser request |
| `GET /api/v1/metrics` | Auth.js session | Browser request |

API key validation: check `X-Verum-API-Key` against `deployments` table — the key is the deployment's `id` (UUID). Simple, no separate key table needed for Phase 4-A.

---

## 8. Error Handling

| Scenario | Behavior |
|---|---|
| `model` not found in `model_pricing` | Store `cost_usd = 0`, log warning. Never block trace ingestion. |
| Judge LLM returns malformed JSON | Retry once. If still fails: `judge_score = NULL`, job marked `done`. |
| Judge job fails entirely | Trace remains with `judge_score = NULL`. Dashboard shows "채점 중..." indefinitely (acceptable for Phase 4-A). |
| `POST /api/v1/traces` with invalid `deployment_id` | Return `404`. |
| Feedback for unknown `trace_id` | Return `404`. |

---

## 9. Out of Scope (Phase 4-A)

These are explicitly deferred to later phases:

- **Storing actual prompt/response text in spans** — privacy consideration; opt-in in Phase 5
- **Per-segment latency breakdown** (TTFT, streaming chunks) — Phase 5
- **RAGAS evaluation** (faithfulness, answer_relevancy) — Phase 4-B EXPERIMENT
- **model_pricing management UI** — Phase 5; DB editable via Supabase/direct SQL for now
- **Multi-deployment metrics comparison** — Phase 4-B
- **Real-time trace streaming** (WebSocket/SSE) — Phase 5

---

## 10. ArcanaInsight Dogfood Validation

Phase 4-A is complete when:

1. ArcanaInsight's tarot reading endpoint calls `client.record()` after each Grok call
2. Every call appears in `traces` table within 5 seconds
3. `judge_score` is populated within 60 seconds of trace creation
4. Dashboard shows 7-day chart with real cost and latency data
5. xzawed can click any trace and see the span detail + judge reasoning in the slide-over panel
