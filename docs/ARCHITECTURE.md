---
type: architecture
authority: tier-2
canonical-for: [file-tree, schemas, api-contracts, sdk-surface, adrs, infra]
last-updated: 2026-05-05
status: active
---

# Verum — Architecture

> **Claude instructions:** This file owns the file tree, database schemas, API contracts, SDK surface, and ADR full text.
> Section 2 (Repository Layout) MUST mirror CLAUDE.md §📁 exactly — verify on every change.
> When deciding where a new file belongs, consult §2 before creating anything.
> Authority: CLAUDE.md > this file > LOOP.md for stage details.

---

## 1. System Overview

> **Architecture pivot (2026-04-20):** FastAPI/Uvicorn 제거. 단일 Railway 서비스, 단일 Docker 이미지.
> Node.js(Next.js)가 PID 1로 동작하며 Python worker를 child process로 spawn합니다.
> 두 프로세스는 `verum_jobs` PostgreSQL 테이블로만 협업합니다 — HTTP 결합 없음.

```
  Railway Service: verum (single service, single deploy)
  ┌────────────────────────────────────────────────────────────┐
  │ Container (Node PID 1 + Python worker child)                │
  │                                                             │
  │  ┌──────────────────────────────────────────────────────┐  │
  │  │ Next.js / Node.js  (PID 1, :8080)                    │  │
  │  │  • App Router — UI pages + SDK API (/api/v1/...)     │  │
  │  │  • Auth.js v5 — GitHub OAuth, JWT session            │  │
  │  │  • Drizzle ORM — Postgres direct R/W                 │  │
  │  │  • Server Actions → INSERT INTO verum_jobs           │  │
  │  │  • instrumentation.ts → spawn Python worker ↓        │  │
  │  │                                                      │  │
  │  │  ┌────────────────────────────────────────────────┐  │  │
  │  │  │ Python Worker  (asyncio child process)          │  │  │
  │  │  │  • LISTEN verum_jobs + SKIP LOCKED poll         │  │  │
  │  │  │  • Handlers: analyze / infer / harvest / generate│  │  │
  │  │  │  • Writes results back to Postgres              │  │  │
  │  │  │  • Heartbeat → worker_heartbeat table           │  │  │
  │  │  └────────────────────────────────────────────────┘  │  │
  │  └──────────────────────────────────────────────────────┘  │
  └────────────────────────────────────────────────────────────┘
                           │
                           ▼
              ┌────────────────────────────┐
              │  PostgreSQL 16 + pgvector   │
              │   • verum_jobs  (queue)     │
              │   • worker_heartbeat        │
              │   • users / repos           │
              │   • analyses / inferences   │
              │   • chunks                  │
              └────────────────────────────┘

  External connections:
  ┌──────────┐  GitHub OAuth   ┌─────────────┐
  │  Browser │────────────────→│ Next.js :8080│
  └──────────┘                 └─────────────┘
  ┌──────────┐  SDK HTTP        ┌─────────────┐
  │Connected │─────────────────→│/api/v1/...  │ (Phase 4+)
  │ Service  │                  └─────────────┘
  └──────────┘
```

---

## 2. Repository Layout

> This section MUST mirror CLAUDE.md §📁 exactly. If CLAUDE.md updates its file tree, update this section in the same PR.

```
verum/
├── .claude/                    # Claude Code project-local settings
├── .github/
│   ├── workflows/ci.yml        # GitHub Actions: lint + test
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.md
│   │   └── feature_request.md
│   └── PULL_REQUEST_TEMPLATE.md
├── docs/
│   ├── INDEX.md                # Navigation hub (tier-3)
│   ├── LOOP.md                 # Stage algorithms (tier-2)
│   ├── ARCHITECTURE.md         # This file (tier-2)
│   ├── DECISIONS.md            # ADR index + product-scope decisions (tier-2)
│   ├── ROADMAP.md              # Phase timing + F-IDs (tier-2)
│   ├── WEEKLY.md               # Weekly KPI log (xzawed updates every Friday)
│   ├── GLOSSARY.md             # Vocabulary (tier-3)
│   └── guides/                 # Phase 5+ end-user docs
├── apps/
│   ├── api/                    # Python Worker (asyncio subprocess — ADR-009)
│   │   ├── src/
│   │   │   ├── worker/         # Node.js가 spawn하는 entrypoint
│   │   │   │   ├── main.py     # asyncio.run(run_loop()) — PID는 Node.js가 관리
│   │   │   │   ├── runner.py   # LISTEN/NOTIFY + SKIP LOCKED job dispatch
│   │   │   │   └── handlers/   # analyze.py / infer.py / harvest.py / generate.py
│   │   │   ├── loop/           # The Verum Loop core logic — SACRED (ADR-008)
│   │   │   │   ├── analyze/    # [1] Repo static analysis
│   │   │   │   ├── infer/      # [2] Service intent inference
│   │   │   │   ├── harvest/    # [3] Domain knowledge crawling
│   │   │   │   ├── generate/   # [4] Asset auto-generation
│   │   │   │   ├── deploy/     # [5] SDK injection
│   │   │   │   ├── observe/    # [6] Runtime tracing
│   │   │   │   ├── experiment/ # [7] A/B testing
│   │   │   │   └── evolve/     # [8] Winner promotion
│   │   │   └── db/             # SQLAlchemy models, session factory
│   │   ├── tests/
│   │   ├── alembic/            # Schema SoT (verum_jobs + worker_heartbeat included)
│   │   └── pyproject.toml
│   └── dashboard/              # Next.js 16 — public HTTP 전담 (ADR-009)
│       └── src/
│           ├── app/            # App Router pages + /api/v1/... SDK routes
│           ├── worker/         # spawn.ts — Python worker lifecycle management
│           ├── lib/
│           │   └── db/         # Drizzle ORM client + hand-written schema
│           └── proxy.ts        # Auth.js v5 route protection (Next.js 16 edge-compatible name)
├── packages/
│   ├── sdk-python/             # pip install verum
│   │   ├── src/verum/
│   │   └── pyproject.toml
│   └── sdk-typescript/         # npm install @verum/sdk
│       ├── src/
│       └── package.json
├── examples/
│   └── arcana-integration/     # ArcanaInsight dogfood (Phase 3, F-3.10)
├── Dockerfile                  # Single multi-stage image: Node + Python (ADR-009)
├── docker-compose.yml
├── railway.toml
├── Makefile
├── CLAUDE.md                   # Tier-1 authority — xzawed-only for identity/roadmap
├── README.md
├── README.ko.md
└── LICENSE                     # MIT
```

---

## 3. Stage-to-Module Map

| Stage | Directory | Primary Dependencies |
|---|---|---|
| [1] ANALYZE | `apps/api/src/loop/analyze/` | `ast` (stdlib), `tree-sitter` |
| [2] INFER | `apps/api/src/loop/infer/` | `anthropic` (Claude Sonnet 4.6+) |
| [3] HARVEST | `apps/api/src/loop/harvest/` | `httpx`, `trafilatura`, `playwright` (opt-in, soft import) |
| [4] GENERATE | `apps/api/src/loop/generate/` | `anthropic` (Claude Sonnet 4.6+), `pgvector` — default `GENERATE_MAX_TOKENS=4096`; JSON truncation handled by best-effort repair in `loop/utils.py` |
| [5] DEPLOY | `apps/api/src/loop/deploy/` | `sdk-python`, `sdk-typescript` |
| [6] OBSERVE | `apps/api/src/loop/observe/` | OpenTelemetry SDK |
| [7] EXPERIMENT | `apps/api/src/loop/experiment/` | `scipy` (Bayesian stats) |
| [8] EVOLVE | `apps/api/src/loop/evolve/` | Internal (DB writes only) |

---

## 4. Data Models

All schemas are managed via Alembic migrations. No raw SQL. All datetime fields are UTC.

### `repos`

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` PK | |
| `github_url` | `TEXT` UNIQUE | |
| `owner_user_id` | `UUID` FK → users | |
| `default_branch` | `TEXT` | default `"main"` |
| `last_analyzed_at` | `TIMESTAMPTZ` | |
| `created_at` | `TIMESTAMPTZ` | |

### `analyses`

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` PK | |
| `repo_id` | `UUID` FK → repos | |
| `call_sites` | `JSONB` | list of LLMCallSite |
| `prompt_templates` | `JSONB` | list of PromptTemplate |
| `model_configs` | `JSONB` | |
| `language_breakdown` | `JSONB` | |
| `analyzed_at` | `TIMESTAMPTZ` | |

### `inferences`

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` PK | |
| `repo_id` | `UUID` FK → repos | |
| `analysis_id` | `UUID` FK → analyses | |
| `status` | `VARCHAR(32)` | `pending` / `done` / `error` |
| `domain` | `TEXT` | e.g. `"divination/tarot"` |
| `tone` | `TEXT` | nullable |
| `language` | `TEXT` | BCP-47, nullable |
| `user_type` | `TEXT` | nullable |
| `confidence` | `FLOAT` | nullable |
| `summary` | `TEXT` | nullable — human-readable service description |
| `raw_response` | `JSONB` | full LLM output for debugging |
| `error` | `VARCHAR(1024)` | nullable |
| `created_at` | `TIMESTAMPTZ` | |

> **컬럼 정정 (2026-04-26):** `subdomain`, `inferred_at`, `raw_llm_response` 컬럼은 존재하지 않음. 실제 구현은 `status`, `summary`, `raw_response`, `created_at`을 사용.

### `harvest_sources`

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` PK | |
| `inference_id` | `UUID` FK → inferences | |
| `url` | `TEXT` | 크롤링 대상 URL |
| `title` | `VARCHAR(512)` | nullable |
| `description` | `TEXT` | nullable |
| `status` | `VARCHAR(32)` | `proposed` / `approved` / `rejected` / `crawling` / `done` / `error` |
| `chunks_count` | `INT` | 크롤링 완료 후 생성된 청크 수 |
| `error` | `VARCHAR(1024)` | nullable — 실패/복구 사유 |
| `created_at` | `TIMESTAMPTZ` | stale 감지 기준 컬럼 (`_reset_stale`에서 cutoff 비교) |

> **CRAWLING 복구 규칙 (ADR-014 연관):** 워커 재시작 시 `_reset_stale()`이 `status='crawling' AND created_at < cutoff` 행을 `status='error'`로 일괄 전환한다. `started_at`이 없어 `created_at`을 프록시로 사용한다.

### `chunks`

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` PK | |
| `source_id` | `UUID` FK → harvest_sources (ON DELETE CASCADE) | |
| `inference_id` | `UUID` FK → inferences (ON DELETE CASCADE) | migration 0018 |
| `content` | `TEXT` | raw chunk text |
| `chunk_index` | `INT` | position within source |
| `embedding_vec` | `vector(1024)` | pgvector column — Voyage AI voyage-3.5 embeddings |
| `ts_content` | `TSVECTOR` | for BM25 hybrid search |
| `metadata` | `JSONB` | `{"domain": ..., "source_url": ...}` |
| `created_at` | `TIMESTAMPTZ` | |

> **컬럼 정정 (2026-04-26):** `harvest_source_id` → `source_id`. `embedding` JSONB는 migration 0016에서 제거됨; `embedding_vec` (pgvector)가 SoT. `embedding_vec`/`ts_content`는 Drizzle 스키마에서 생략됨 (JS에서 정의 불가).

### `generations`

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` PK | |
| `inference_id` | `UUID` FK → inferences | |
| `status` | `TEXT` | `"pending"` / `"done"` / `"error"` |
| `error` | `TEXT` | nullable |
| `generated_at` | `TIMESTAMPTZ` | nullable |
| `created_at` | `TIMESTAMPTZ` | |

### `prompt_variants`

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` PK | |
| `generation_id` | `UUID` FK → generations | |
| `variant_type` | `TEXT` | `"original"` / `"cot"` / `"few_shot"` / `"role_play"` / `"concise"` |
| `content` | `TEXT` | full prompt text with {variable} placeholders |
| `variables` | `JSONB` | list of variable names |
| `created_at` | `TIMESTAMPTZ` | |

### `rag_configs`

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` PK | |
| `generation_id` | `UUID` FK → generations | |
| `chunking_strategy` | `TEXT` | `"recursive"` / `"semantic"` |
| `chunk_size` | `INT` | default 512 |
| `chunk_overlap` | `INT` | default 50 |
| `top_k` | `INT` | default 5 |
| `hybrid_alpha` | `FLOAT` | 0.0–1.0 (higher = more vector weight) |
| `created_at` | `TIMESTAMPTZ` | |

### `eval_pairs`

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` PK | |
| `generation_id` | `UUID` FK → generations | |
| `query` | `TEXT` | realistic user query |
| `expected_answer` | `TEXT` | outline of correct answer |
| `context_needed` | `BOOL` | whether RAG context is required |
| `created_at` | `TIMESTAMPTZ` | |

### `deployments`

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` PK | |
| `generation_id` | `UUID` FK → generations (CASCADE) | |
| `status` | `VARCHAR(32)` | `"canary"` / `"full"` / `"rolled_back"` / `"archived"` |
| `traffic_split` | `JSONB` | `{"baseline": 0.9, "variant": 0.1}` |
| `error_count` | `INT` | default 0 |
| `total_calls` | `INT` | default 0 |
| `experiment_status` | `TEXT` | `"idle"` / `"running"` / `"completed"` |
| `current_baseline_variant` | `TEXT` | active variant name; default `"original"` |
| `api_key_hash` | `TEXT` | SHA-256 hash of the plaintext `vk_` key (migration 0014) |
| `created_at` | `TIMESTAMPTZ` | |
| `updated_at` | `TIMESTAMPTZ` | |

### `traces`

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` PK | |
| `deployment_id` | `UUID` FK → deployments | not nullable |
| `variant` | `TEXT` | `"baseline"` or variant name; default `"baseline"` |
| `user_feedback` | `SMALLINT` | nullable — `1` (positive) / `-1` (negative) |
| `judge_score` | `DOUBLE PRECISION` | nullable — LLM-as-Judge score |
| `created_at` | `TIMESTAMPTZ` | |

### `spans`

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` PK | |
| `trace_id` | `UUID` FK → traces | |
| `model` | `TEXT` | |
| `input_tokens` | `INT` | default 0 |
| `output_tokens` | `INT` | default 0 |
| `latency_ms` | `INT` | default 0 |
| `cost_usd` | `NUMERIC(10,6)` | default 0 |
| `error` | `TEXT` | nullable |
| `started_at` | `TIMESTAMPTZ` | |
| `span_attributes` | `JSONB` | nullable — raw OTLP span attributes (migration 0023) |

### `experiments`

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` PK | |
| `deployment_id` | `UUID` FK → deployments (CASCADE) | |
| `baseline_variant` | `TEXT` | variant name being used as baseline |
| `challenger_variant` | `TEXT` | variant name being tested |
| `status` | `TEXT` | `"running"` / `"converged"` |
| `winner_variant` | `TEXT` | nullable until decided |
| `confidence` | `DOUBLE PRECISION` | nullable |
| `baseline_wins` | `INT` | Bayesian win count for baseline; default 0 |
| `baseline_n` | `INT` | total baseline observations; default 0 |
| `challenger_wins` | `INT` | Bayesian win count for challenger; default 0 |
| `challenger_n` | `INT` | total challenger observations; default 0 |
| `win_threshold` | `DOUBLE PRECISION` | Bayesian stopping threshold; default 0.6 |
| `cost_weight` | `DOUBLE PRECISION` | cost penalty weight in winner score; default 0.1 |
| `started_at` | `TIMESTAMPTZ` | |
| `converged_at` | `TIMESTAMPTZ` | nullable |

### EVOLVE — deployment updates (no separate table)

The EVOLVE stage does not use a dedicated table. Winner promotion and traffic updates are written back to the `deployments` table via `current_baseline_variant`, `traffic_split`, and `experiment_status` columns. The `experiments` table records the concluded experiment and winner.

---

## 5. API Surface

> **Architecture pivot (2026-04-20):** 모든 HTTP 엔드포인트는 **Next.js App Router**가 서빙합니다.
> FastAPI REST 서버는 제거됐습니다. `/health`는 `apps/dashboard/src/app/health/route.ts`,
> SDK API(`/api/v1/...`)는 `apps/dashboard/src/app/api/v1/.../route.ts`로 구현됩니다.
> Loop 실행은 Server Action → `verum_jobs` enqueue → Python worker 처리 순서로 동작합니다.

Base path: `/api/v1` (Next.js route). All endpoints return JSON. Authentication: Auth.js v5 JWT (Phase 1+).

> **Implementation status legend:** ✅ Implemented | 🔲 Phase 4+

### Health

| Method | Path | Description | Status |
|---|---|---|---|
| GET | `/health` | Returns `{"status": "ok"}` — pure liveness probe, no DB I/O | ✅ |

### [1] ANALYZE

| Method | Path | Description | Status |
|---|---|---|---|
| POST | `/api/v1/analyze` | Start analysis job for a repo | ✅ |
| GET | `/api/v1/analyze/{analysis_id}` | Get analysis result | ✅ |
| GET | `/api/v1/repos/{repo_id}/analyses` | List analyses for a repo | 🚧 planned |

### [2] INFER

| Method | Path | Description | Status |
|---|---|---|---|
| POST | `/api/v1/infer` | Run inference on an analysis | ✅ |
| GET | `/api/v1/infer/{inference_id}` | Get inference result | ✅ |
| PATCH | `/api/v1/infer/{inference_id}/confirm` | User confirms or overrides inference | ✅ |

### [3] HARVEST

> **Note:** HARVEST is driven by the job queue (Server Action → `verum_jobs`). There are no direct `/api/v1/harvest/` HTTP endpoints — source proposal, approval, and crawl are handled via job payloads and status polling through the ANALYZE/INFER polling routes.

| Method | Path | Description | Status |
|---|---|---|---|
| POST | `/api/v1/harvest/propose` | LLM proposes sources; returns list for user approval | 🚧 planned |
| POST | `/api/v1/harvest/start` | Start crawl with approved sources | 🚧 planned |
| GET | `/api/v1/harvest/{harvest_id}` | Get harvest status + result | 🚧 planned |
| POST | `/api/v1/retrieve-sdk` | Hybrid search over chunks (SDK endpoint) | ✅ |

### [4] GENERATE

| Method | Path | Description | Status |
|---|---|---|---|
| POST | `/api/v1/generate` | Generate assets from harvest | ✅ |
| GET | `/api/v1/generate/{asset_id}` | Get generated assets | ✅ |
| PATCH | `/api/v1/generate/{asset_id}/approve` | User approves generated assets | ✅ |

### [5] DEPLOY

| Method | Path | Description | Status |
|---|---|---|---|
| POST | `/api/v1/deploy` | Deploy approved assets | ✅ |
| GET | `/api/v1/deploy/{deployment_id}/config` | Get deployment config (SDK polling) | ✅ |
| POST | `/api/v1/deploy/{deployment_id}/traffic` | Adjust traffic split | ✅ |
| POST | `/api/v1/deploy/{deployment_id}/rollback` | Rollback to baseline | ✅ |

### [6] OBSERVE

| Method | Path | Description | Status |
|---|---|---|---|
| POST | `/api/v1/traces` | Ingest trace (SDK → API) | ✅ |
| GET | `/api/v1/traces` | List traces (paginated, filterable) | ✅ |
| GET | `/api/v1/traces/{trace_id}` | Get trace + spans | ✅ |
| GET | `/api/v1/metrics` | Aggregated cost/latency/quality metrics | ✅ |

### [7] EXPERIMENT

> **Note:** Experiments are created by the Python worker automatically (via `_experiment_loop()` in `runner.py`), not by a direct HTTP POST. There is no `POST /api/v1/experiments` endpoint.

| Method | Path | Description | Status |
|---|---|---|---|
| GET | `/api/v1/experiments` | List experiments for a deployment | ✅ |
| GET | `/api/v1/experiments/{experiment_id}` | Get experiment result + Bayesian confidence | ✅ |

### [8] EVOLVE

EVOLVE is triggered automatically as a `verum_jobs` worker job when an experiment converges (no direct HTTP trigger endpoint). Winner promotion, traffic update, and experiment archive are written back to `deployments` and `experiments` tables by the Python worker.

| Method | Path | Description | Status |
|---|---|---|---|
| GET | `/api/v1/experiments/{experiment_id}` | Check experiment status + winner (shared with [7]) | ✅ |

### MCP (Model Context Protocol)

| Method | Path | Description | Status |
|---|---|---|---|
| POST | `/api/mcp` | MCP Streamable HTTP endpoint — API key auth (`Authorization: Bearer` or `X-Verum-API-Key`). Tools: `get_experiments`, `get_traces`, `get_metrics`, `approve_variant` | ✅ |

### Misc / Infrastructure

| Method | Path | Description | Status |
|---|---|---|---|
| POST | `/api/repos/{repo_id}/analyze` | Enqueue analyze job for a specific repo (rate-limited, JWT session, returns 202) | ✅ |
| POST | `/api/v1/csp-report` | CSP violation report ingestion — logs to console, returns 204, no auth required | ✅ |

---

## 6. SDK Surface

Both SDKs follow the same two-phase non-invasive integration pattern. See [docs/INTEGRATION.md](INTEGRATION.md) for a full guide.

### Python SDK (`verum`) — Phase 1

```python
import verum.openai  # 1-line — patches OpenAI client in-process

from openai import OpenAI
import os

client = OpenAI()
resp = client.chat.completions.create(
    model="gpt-4o",
    messages=[...],
    extra_headers={"x-verum-deployment": os.environ["VERUM_DEPLOYMENT_ID"]},
)
# resp is a standard ChatCompletion — no surface change
```

RAG retrieval and feedback remain available as standalone helpers:

```python
from verum import retrieve, feedback

chunks = await retrieve(query="어떤 카드가 나왔나요?", collection_name="arcana-tarot-knowledge", top_k=5)
await feedback(trace_id="...", score=1)
```

### TypeScript SDK (`@verum/sdk`) — Phase 1

```typescript
import "@verum/sdk/openai";  // 1-line — patches OpenAI client in-process
import OpenAI from "openai";

const client = new OpenAI();
const resp = await client.chat.completions.create({
  model: "gpt-4o",
  messages: [...],
  extra_headers: { "x-verum-deployment": process.env.VERUM_DEPLOYMENT_ID! },
});
// resp is a standard ChatCompletion — no surface change
```

> **Legacy v0 API:** `verum.Client.chat()` and `VerumClient.chat()` are deprecated and emit `DeprecationWarning`. Migrate via [docs/MIGRATION_v0_to_v1.md](MIGRATION_v0_to_v1.md).

---

## 7. Architecture Decision Records

Full ADR text lives here. The index and product-scope decisions are in [DECISIONS.md](DECISIONS.md).

### ADR-001: pgvector Only — No External Vector DB

**Status:** Accepted | **Date:** 2026-04-19

**Decision:** All vector storage uses PostgreSQL + pgvector. Pinecone, Weaviate, Qdrant, Chroma, and any other external vector database are prohibited.

**Why:** pgvector is sufficient for Verum's scale. xzawed has deep PostgreSQL expertise. A single data store reduces operational complexity and aligns with the `docker compose up` self-hosting constraint. Splitting vector data into a second database adds overhead with no benefit at Phase 0–3 scale.

**Trade-off accepted:** At very high volumes (>10M chunks), dedicated vector DBs offer better ANN performance. Cross that bridge only if metrics demand it, after Phase 4.

**Revisit trigger:** Hybrid search P95 latency exceeds 500ms at production query volume.

---

### ADR-002: No LangChain / LlamaIndex in Any Package

**Status:** Accepted | **Date:** 2026-04-19

**Decision:** Neither `langchain` nor `llama-index` may be imported in `apps/`, `packages/`, or `examples/`.

**Why:** Verum is an alternative to the abstraction layer these frameworks provide. Depending on them would make Verum's loop a thin wrapper over a competitor's abstractions, import hundreds of transitive dependencies, and create positioning confusion.

**Trade-off accepted:** Must implement chunking, embedding, retrieval, and prompt management primitives directly. Intentional — these are Verum's core differentiators.

**Revisit trigger:** Never. Product identity decision.

---

### ADR-003: FastAPI + Uvicorn

**Status:** ~~Accepted~~ **Superseded by ADR-009** | **Date:** 2026-04-19 | **Superseded:** 2026-04-20

**Decision (original):** API is FastAPI + Uvicorn. Django, Flask, and Litestar are prohibited.

**Supersession reason:** Architecture pivot to single Railway container. FastAPI/Uvicorn 완전 제거. 공개 HTTP는 Next.js가 전담하고 Python은 asyncio worker child process로만 동작. See ADR-009.

---

### ADR-004: SQLAlchemy 2 Async + Alembic — No Raw SQL

**Status:** Accepted | **Date:** 2026-04-19

**Decision:** All database access goes through SQLAlchemy 2 async session. All schema changes go through Alembic. Raw SQL strings in application code are prohibited.

**Why:** SQLAlchemy 2 async integrates cleanly with FastAPI. Alembic provides reproducible schema history for self-hosted deployments. Raw SQL bypasses type safety and migration tracking.

---

### ADR-005: Async-first Python

**Status:** Accepted | **Date:** 2026-04-19

**Decision:** All I/O-bound functions in `apps/api/` and `packages/sdk-python/` must be `async def`. Synchronous I/O is prohibited in these packages.

**Why:** Blocking I/O stalls the asyncio worker event loop. HARVEST (crawler) and OBSERVE (SDK instrumentation) are heavily I/O-bound.

---

### ADR-006: Next.js 16 App Router + React 19

**Status:** Accepted (updated 2026-04-20) | **Date:** 2026-04-19

**Decision:** Dashboard is Next.js 16 App Router (standalone output), React 19, TypeScript strict, Tailwind CSS v4, Recharts, Zustand, Auth.js v5 (`next-auth@5` beta), Drizzle ORM.

**Why:** Server components reduce bundle size. React 19 server actions simplify forms and job enqueuing. Auth.js v5 covers GitHub OAuth natively. Drizzle ORM provides type-safe Postgres access without a separate API layer (replaces `apiFetch` + FastAPI after ADR-009 pivot).

---

### ADR-007: Never Hardcode Embedding Dimensions

**Status:** Accepted | **Date:** 2026-04-19

**Decision:** Embedding dimensions are always read from `harvest_sources.embedding_dim` at runtime. No numeric dimension constant may appear in application code.

**Why:** Verum supports multiple embedding models (Voyage AI voyage-3.5 = 1024). Hardcoding breaks when the user switches models. Dimension is persisted at collection creation and propagated from `harvest_sources`.

**Trade-off accepted:** Requires a DB read before vector operations. Cached per-collection in memory after first load.

---

### ADR-008: `apps/api/src/loop/` Directory Structure is Sacred

**Status:** Accepted | **Date:** 2026-04-19

**Decision:** The eight subdirectories under `apps/api/src/loop/` must always exist and map 1:1 to The Verum Loop stages in CLAUDE.md. Adding or removing a stage requires a CLAUDE.md update first (xzawed-only edit).

**Why:** The directory structure enforces the discipline of answering "which stage does this belong to?" for every new feature. Cross-cutting concerns (auth, logging) belong in `integrations/` or `db/`, never as loop stages.

**Trade-off accepted:** Logic spanning stages (e.g., an INFER helper reading ANALYZE output) must be placed in the stage that *produces* the output and passed explicitly.

**Revisit trigger:** A new loop stage is proposed. CLAUDE.md updates first; then this ADR is superseded.

---

### ADR-009: Single Container — Node.js PID 1 + Python Worker Child + Postgres Job Queue

**Status:** Accepted | **Date:** 2026-04-20 | **Supersedes:** ADR-003

**Decision:** Verum runs as a single Railway service with a single Docker image. Node.js (Next.js) is PID 1. Python runs as a child process spawned by Node.js at boot via `instrumentation.ts`. The two runtimes communicate exclusively through the `verum_jobs` PostgreSQL table — no HTTP between them.

**Why:**
- Railway의 hard constraint: 서비스는 반드시 1개. 2개 이상이면 배포·관리 복잡도 급증.
- Python ML 스택 보존 (tree-sitter, trafilatura, RAGAS, pgvector 임베딩 등).
- HTTP 결합 제거 — `VERUM_API_URL`, 내부 토큰, URL 동기화 문제 전부 사라짐.
- Long-running batch (ANALYZE, HARVEST)가 HTTP timeout 없이 실행 가능.
- SDK는 단일 URL만 알면 됨 (`verum.dev`).

**Constraints:**
- `ENV HOSTNAME=0.0.0.0` must be set in Dockerfile — Docker auto-injects `HOSTNAME=<container_id>` which prevents Next.js standalone from binding to all interfaces.
- Python worker crash는 Node.js가 respawn (backoff 포함). 5회 연속 crash 시 healthcheck 503 → Railway 컨테이너 재시작.
- `verum_jobs.status = 'running'` 행은 부팅 시 `queued`로 reset (stale job recovery).

**Trade-off accepted:** 단일 컨테이너이므로 Node과 Python이 같은 머신의 CPU/메모리를 공유. Phase 4+ 부하 급증 시 Railway replica 증설 또는 worker 분리 서비스 재검토.

**Revisit trigger:** 단일 컨테이너의 메모리/CPU 한계 도달 시 (Phase 4+ 예상).

---

## 8. Infrastructure & Deployment

### Docker (Single Image — ADR-009)

단일 멀티스테이지 `Dockerfile` (repo root). Node.js + Python 모두 포함.

```
Stage 1: web-build   — Next.js standalone 빌드 (node:20-slim)
Stage 2: py-build    — Python 의존성 wheel 설치 (python:3.13-slim)
Stage 3: runtime     — python:3.13-slim base + NodeSource Node.js 20 overlay
                       ENV HOSTNAME=0.0.0.0  ← 필수 (Docker HOSTNAME 주입 차단)
                       ENV NODE_ENV=production
                       CMD ["node", "server.js"]
```

Self-hosting: `docker compose up` 으로 전체 스택 실행. DB는 별도 `postgres:16` 컨테이너.

### Railway (Initial Cloud)

- **단일 서비스**: `verum` — `Dockerfile` (repo root), `railway.toml`
- **DB**: Railway PostgreSQL plugin (pgvector extension 활성화 필수)
- **Healthcheck**: `/health` path, 60s timeout, `ON_FAILURE` restart policy
- **필수 env vars**: `DATABASE_URL`, `AUTH_SECRET`, `AUTH_GITHUB_ID`, `AUTH_GITHUB_SECRET`, `ANTHROPIC_API_KEY`, `VOYAGE_API_KEY`
- **레거시 제거**: `VERUM_API_URL`, `VERUM_INTERNAL_API_TOKEN`, `NEXTAUTH_SECRET` — Railway 대시보드에서 삭제

### Image Size Constraint

Final Docker image must be under 1GB. Use multistage builds.

### Deployment Pre-Flight Checklist

Dockerfile, `alembic/`, 또는 `apps/api/src/worker/` 변경 시 push 전 필수:

```bash
make docker-healthcheck   # Railway 환경(PORT=8080, HOSTNAME 미주입) 로컬 재현
```

성공 신호: 컨테이너 로그에 `Local: http://0.0.0.0:8080` 확인.

### CI/CD

`.github/workflows/ci.yml`:
- `ruff`, `pylint`, `bandit`, `mypy` on Python
- `tsc --noEmit`, `eslint` on TypeScript
- `pytest` with coverage (Phase 2+: ≥ 80%)
- Merge blocked on failure

---

### ADR-010: Lazy Initialization for `next build` Compatibility

**Status:** Accepted | **Date:** 2026-04-25

**Decision:** Every external client (database pool, OpenAI, Anthropic, Redis, etc.) instantiated in a Next.js route module **must** be wrapped in a lazy getter function. Module-scope instantiation is forbidden.

```typescript
// ❌ Forbidden — throws at build time when env var is absent
const openai = new OpenAI();

// ✅ Required pattern
let _openai: OpenAI | null = null;
function getOpenAI() {
  if (!_openai) _openai = new OpenAI();
  return _openai;
}
```

**Why:** `next build` runs "Collecting page data" which imports every route module in a Docker build environment that has **no** runtime secrets (`DATABASE_URL`, `OPENAI_API_KEY`, etc.). Both the `pg` Pool and the `openai` SDK validate their required configuration at instantiation time — calling them at module scope causes every Railway build to fail with a cryptic env-var error.

Discovered in two sequential Railway build failures (2026-04-24/25):
1. `DATABASE_URL` in `lib/db/client.ts` — moved inside `getDb()`
2. `OPENAI_API_KEY` in `api/v1/retrieve-sdk/route.ts` — moved inside `getOpenAI()`

**Trade-off accepted:** Singleton state lives in a module-level variable. The first real request bears the one-time initialization cost. This is the standard Next.js + external client pattern and is safe in a single-process Node.js server.

**Revisit trigger:** If Next.js adds a native "defer to runtime" annotation or if the app moves to Edge Runtime where module-level singletons behave differently.

---

### ADR-011: Codecov Action Pinned to v5

**Status:** Accepted | **Date:** 2026-04-26

**Decision:** `codecov/codecov-action` is pinned to **v5** in all CI workflows.

**Context:** v4 bundled uploader suffered a shasum/GPG regression (2026-04-26); v5 switches to `codecov-cli` which avoids this issue. `fail_ci_if_error: true` is set so coverage upload failures block the merge — we want to know when coverage data is missing, not silently skip it.

**Trade-off accepted:** Pinning to v5 means we must track Codecov major releases manually. Acceptable given that Codecov breaking changes are rare and the alternative (allowing automatic major upgrades) risks supply-chain surprises.

---

### ADR-012: Integration Test via Production-Image Compose + Mock Provider Stack

**Status:** Accepted | **Date:** 2026-04-26

**Decision:** Full-loop integration tests (`docker-compose.integration.yml`) build and run the **same root `Dockerfile`** used in Railway production, with all external APIs (Anthropic, OpenAI, GitHub, git-http) replaced by a FastAPI mock stack.

**Context:** Unit tests with mocks proved insufficient — mock/prod divergence masked broken migrations and wiring issues. Running the real container image catches Dockerfile regressions, Node→Python spawn failures, and end-to-end job routing bugs that mocks miss.

**Key design choices:**
- `VERUM_TEST_MODE=1` enables 5+2 env-gated test hooks; production business logic in `apps/api/src/loop/**` is **not touched**.
- `ANTHROPIC_BASE_URL`, `OPENAI_BASE_URL`, `GITHUB_API_URL` env overrides redirect traffic to mock containers.
- `/test/login` bypass endpoint is gated behind `VERUM_TEST_MODE` and returns a fixed test session.
- CI runs nightly + `workflow_dispatch`; job is informational (non-blocking) until a 2-week stability baseline is confirmed.

See `docker-compose.integration.yml` for the full service definition.

---

### ADR-013: SQLAlchemy `text()` / PostgreSQL Cast Syntax

**Status:** Accepted | **Date:** 2026-04-24

**Decision:** In all SQLAlchemy `text()` queries, PostgreSQL-style inline casts (`:param::type`) are **forbidden**. Use ANSI `CAST(:param AS type)` exclusively.

```python
# ❌ Forbidden — SQLAlchemy skips bind-param detection, sends literal ":param" to asyncpg
text("INSERT INTO t (col) VALUES (:val::jsonb)")

# ✅ Required
text("INSERT INTO t (col) VALUES (CAST(:val AS jsonb))")
```

**Why:** SQLAlchemy's `text()` parser treats `:name` as a bind parameter **only when** it is not immediately followed by `::`. When `::` is present, the parser intentionally skips the token to avoid ambiguity with PostgreSQL's cast operator. As a result, the literal string `:val` (colon included) is forwarded to asyncpg, which raises a syntax error:

```
sqlalchemy.exc.ProgrammingError: (asyncpg.exceptions.PostgresSyntaxError)
syntax error at or near ":"
STATEMENT: INSERT INTO t (col) VALUES (:val::jsonb)
```

This manifests silently in development if you happen to test with mock sessions, but explodes at runtime against a real Postgres connection. Found in five separate locations across `loop/generate/repository.py`, `loop/deploy/repository.py`, `loop/deploy/orchestrator.py`, `loop/evolve/repository.py`, and `worker/runner.py` during integration test stabilisation (2026-04-24).

**Trade-off accepted:** `CAST(:x AS jsonb)` is slightly more verbose than `:x::jsonb`. The verbosity is worth the deterministic behaviour.

**Revisit trigger:** None — this is a permanent rule. SQLAlchemy's behaviour here is intentional and documented.

---

### ADR-014: One SQLAlchemy AsyncSession Per Concurrent Coroutine

**Status:** Accepted | **Date:** 2026-04-25

**Decision:** A single `AsyncSession` instance must **never** be shared across concurrently-executing coroutines. Each coroutine that runs database I/O must acquire its own session via `async with AsyncSessionLocal() as db:`.

```python
# ❌ Forbidden — shared session passed into asyncio.gather fan-out
async def handle_harvest(db, ...):
    await asyncio.gather(*[_harvest_one(db, src) for src in sources])

# ✅ Required — each coroutine owns its session
async def _harvest_one(source_id, url):
    async with AsyncSessionLocal() as own_db:
        ...  # use own_db exclusively
```

**Why:** SQLAlchemy's async session is not thread-safe or coroutine-safe for concurrent use. When multiple coroutines share one session and interleave `await` points, `execute()` / `commit()` calls can overlap. The result is silent data loss, phantom commits, or `InvalidRequestError` crashes. This manifested in `handle_harvest`: three concurrent `_harvest_one` coroutines shared the handler's session, causing commit races that left `harvest_sources` rows stuck in `crawling` status even after successful crawls.

**Trade-off accepted:** Opening one session per concurrent unit has connection-pool overhead. At `Semaphore(3)` concurrency this is negligible. If concurrency ever scales to O(100), evaluate a connection-per-task overhead budget first.

**Revisit trigger:** If a profiling session shows connection pool exhaustion at high HARVEST concurrency, revisit whether a read-only shared session for SELECT-only paths is acceptable (writes must still own their session).

---

### ADR-015: 공통 mock 대상 모듈은 직접 단위 테스트 필수

**Status:** Accepted | **Date:** 2026-04-25

**Decision:** 여러 테스트 파일에서 `jest.mock()` 또는 `unittest.mock.patch()`로 통째로 교체되는 유틸리티 모듈은 **반드시 해당 모듈을 직접 import하는 전용 테스트 파일**을 가져야 한다.

```typescript
// ❌ 금지 — handlers.ts를 사용하는 모든 route 테스트가 이렇게 mock하면
// handlers.ts 자체는 한 줄도 실행되지 않는다
jest.mock("@/lib/api/handlers", () => ({ getAuthUserId: jest.fn() }));

// ✅ 필수 — src/lib/api/__tests__/handlers.test.ts 에서 직접 테스트
import { getAuthUserId, createGetByIdHandler } from "../handlers";
// auth, rateLimit만 mock하고 handlers.ts 로직은 실제로 실행
```

```python
# Python도 동일 — patcher로 완전히 대체되는 모듈은 직접 테스트 필요
# ✅ tests/worker/test_payloads.py: AnalyzePayload 직접 호출로
#    validate_repo_url / validate_branch 오류 경로 커버
```

**Why (재발 원인):** 2026-04-25 SonarCloud Quality Gate가 "New Code Coverage 78.7% < 80%"로 실패했다. 전체 Python 커버리지(88%)는 충분했지만 SonarCloud는 **참조 커밋 이후 추가된 신규 라인만** 집계한다. 신규 파일인 `apps/dashboard/src/lib/api/handlers.ts`(26줄)는 route 테스트들이 전부 mock하기 때문에 0% 커버리지였고, `src/worker/payloads.py`의 새 validator 오류 경로(3줄)도 미커버였다. 이 두 파일의 미커버 라인이 TypeScript 신규 라인 풀을 끌어내려 게이트를 통과하지 못한 것이다.

**SonarCloud "New Code" 작동 방식 (필독):**
- `previous_version` 모드: 직전 소나 버전(= 직전 push의 `sonar.projectVersion`) 이후 추가·수정된 라인만 신규 코드로 집계
- 신규 라인 커버리지 = (신규 라인 중 hit된 것) / (신규 라인 전체 실행 가능 줄 수)
- 임계값: **80%** (sonar-project.properties `sonar.qualitygate.wait=true`)
- Python(coverage.xml)과 TypeScript(LCOV) **모두 합산**된다 — Python만 높아도 TS가 낮으면 전체가 낮아짐

**방지 규칙:**
1. 새 유틸리티 파일(`lib/`, `utils/`, `helpers/` 등)을 추가할 때 **동일 PR에 직접 테스트 파일을 포함**한다.
2. `jest.mock('경로')` 또는 `patch('경로')` 가 5곳 이상 존재하는 모듈은 별도 직접 테스트 대상으로 표시한다.
3. 신규 Python validator / error path는 해당 모듈의 테스트 파일에서 직접 `pytest.raises`로 커버한다.

**Trade-off accepted:** mock 대상 파일에 테스트를 추가하면 `auth`, `rateLimit` 등 외부 의존을 한 번 더 mock해야 한다. 이는 약간의 보일러플레이트지만, SonarCloud 게이트 실패와 디버깅 비용보다 훨씬 저렴하다.

**Revisit trigger:** SonarCloud 임계값이 80% 미만으로 낮아지거나, `sonar.coverage.exclusions`에 해당 파일을 추가하는 경우 (단, 이는 증상을 가리는 것이지 해결책이 아님).

---

### ADR-016: No LLM Proxy — Direct Call Only

**Status:** Accepted | **Date:** 2026-04-25

**Decision:** Verum must NEVER route user LLM calls through a proxy gateway. The SDK only instruments the call in-process (monkey-patch or OTLP exporter). Verum's servers are never in the hot path of a user's LLM call.

**Why:** A gateway pattern introduces an inherent SPOF: if Verum's gateway is down, the user's service is down. This cannot be fixed with fail-open inside the SDK library — once `base_url` points to Verum's gateway, the call goes to Verum, not OpenAI. The user has no recourse. This violates the zero-invasiveness principle. Analysis across 7 invasiveness dimensions (SPOF, performance, security, cost, debugging, code changes, functional integrity) confirmed the gateway scores 5/5 on the SPOF dimension.

**Trade-off accepted:** Without a proxy, Verum cannot intercept and modify LLM responses in real time. All Verum interventions happen at the system-prompt / messages level only. This is acceptable for the current use case (prompt A/B testing).

**Revisit trigger:** If a future use case requires response-level intervention (e.g., output filtering), evaluate a sidecar proxy pattern where the user's service explicitly opts in (not a mandatory gateway).

---

### ADR-017: Fail-Open SDK — 5-Layer Safety Net

**Status:** Accepted | **Date:** 2026-04-25

**Decision:** Every Verum SDK operation that contacts the Verum server MUST fail open — i.e., if Verum is unreachable, slow, or returning errors, the user's original request passes through unchanged. The SDK implements 5 layers:

1. **Hard timeout 200ms**: Any Verum config fetch that takes >200ms is aborted.
2. **Circuit breaker**: After 5 consecutive failures, the circuit opens for 300 seconds. During the open window, all requests skip the Verum fetch and return `fail_open` immediately.
3. **Fresh cache (60s TTL)**: Successful config fetches are cached for 60 seconds.
4. **Stale cache (24h TTL)**: If the fresh cache is expired but the stale cache (24h) is still valid, the stale value is served rather than hitting the network.
5. **Fail-open fallback**: If all layers fail (no cache, circuit open, timeout), the original messages are returned unchanged and the variant is set to "baseline".

**Why:** The zero-invasiveness principle requires that Verum's availability does not affect the user's service availability. If Verum has a 30-minute outage and the SDK propagates errors, we have violated the core product promise.

**Trade-off accepted:** Stale configs (up to 24h) may be served. This means a traffic split change made in the dashboard takes up to 24h to fully propagate in the worst case (fresh TTL miss + stale hit). Acceptable trade-off for reliability.

**Revisit trigger:** If users report that traffic split changes are not reflected quickly enough, reduce stale TTL or add a push invalidation mechanism.

---

### ADR-018: Zero-Code-Change SDK Auto-Patch via `.pth` + `NODE_OPTIONS`

**Status:** Accepted — 2026-05-01

**Context:**

Phase 1 SDK integration (`import verum.openai`) requires a one-line code change to user services. For environments where code changes are not possible (no source access, legacy deployments, zero-touch policy), an even lighter integration path is needed.

**Decision:**

- **Python**: Ship `verum-auto.pth` inside the `verum` wheel (via hatchling `force-include`). Python's `site.py` processes `.pth` files at interpreter startup; lines starting with `import` are executed as Python code. The file contains `import verum._auto`. `verum/_auto.py` reads `VERUM_API_URL` and `VERUM_API_KEY` env vars; if configured and not disabled, it imports `verum.openai` and `verum.anthropic` to monkey-patch the clients. No code change needed in the user's service.
- **TypeScript / Node.js**: Ship `@verum/sdk/auto` (exported from `packages/sdk-typescript/src/auto.ts`). Users set `NODE_OPTIONS="--require @verum/sdk/auto"`. Node.js pre-requires the module before user code, triggering the same env-var check and conditional patching.

Both implementations:
- Check `VERUM_DISABLED` (values `1`, `true`, `yes`) and skip patching if set
- Silently swallow `ImportError` / `require()` failure (openai/anthropic not installed → no-op)
- Apply ADR-016 and ADR-017 safety guarantees (no proxy, fail-open)

**Alternatives Rejected:**

- `sitecustomize.py` — executed before site-packages, but only in system Python installations. Breaks in virtualenvs. Not reliable for user deployments.
- Gateway/proxy approach — rejected in ADR-016. Still SPOF.
- Automatic patching on `pip install` via post-install hooks — pip intentionally disables arbitrary post-install scripts for security.

**Consequences:**

- `pip install verum` now silently auto-patches Python interpreters that have `VERUM_API_URL` set. Users who want to opt out must set `VERUM_DISABLED=1`.
- The `.pth` file (`verum-auto.pth`) must be kept in sync with `_auto.py` imports if new providers are added.
- Tested: 7 Python unit tests (`test_auto.py`) + 8 TypeScript unit tests (`auto.test.ts`), both 100% coverage on new files.

---

### ADR-019: ActivationCard v2 — No-PR One-Click Activation

**Status:** Accepted — 2026-05-01

**Context:**

ActivationCard v1 (pre-PR #104) offered two integration paths by automatically creating GitHub Pull Requests to the user's repository — one adding OTLP env vars (Phase 0) and another adding `import verum.openai` + `extra_headers` (Phase 1). This approach had several problems:

- Required elevated GitHub OAuth scopes (`repo` write access) just to show a "getting started" UI.
- Created commits in the user's service repository without explicit per-commit consent.
- The PR-based flow was complicated to implement and fragile: branch naming, file path sanitization, Git Data API 7-step pipeline.
- Many users just want env vars — they do not want Verum touching their repo at all.

**Decision:**

Remove GitHub PR creation from the activation flow entirely. Replace with a synchronous one-click endpoint:

- `POST /api/repos/[id]/activate` (JWT session auth):
  1. Verifies repo ownership.
  2. Finds the latest approved generation.
  3. 409 if a deployment already exists for that generation.
  4. Generates `api_key = "vk_" + crypto.randomBytes(32).hex()`.
  5. Stores only `SHA-256(api_key)` in `deployments.api_key_hash` — plaintext never persisted (GitHub PAT model).
  6. Inserts `deployments` + `experiments` rows atomically.
  7. Returns `{ deployment_id, api_key, verum_api_url }` with HTTP 201.

- ActivationCard 5-state machine: `no-generation → ready → activated → waiting → connected`.
  - `activated`: key shown once in Python/Node.js env-var tabs with "Copy all" button.
  - `waiting`: polls `GET /api/v1/activation/[repoId]` every 5 s; transitions to `connected` when `deployment.trace_count > 0`.

**Alternatives Rejected:**

- Keep PR flow — creates GitHub commits without fine-grained user consent; requires write OAuth scope.
- Show key inline without state machine — key would be lost on page reload; need explicit "I've saved these" acknowledgment.

**Consequences:**

- `sdk_pr_requests` table and associated routes (`/api/repos/[id]/sdk-pr`) remain in the codebase but are no longer surfaced in the ActivationCard UI. They can be removed in a future cleanup PR.
- Users get credentials in ~200ms (synchronous DB insert) vs. the previous 5-30s GitHub API round-trip.
- The activation flow no longer requires GitHub write access — reduces OAuth scope surface.
- Tested: 6 unit tests for activate route (401, 404, 422, 409, 201, key uniqueness) + 5 tests for activation data route (including `trace_count: 0` partial branch).

---

---

### ADR-020: Signal-Specific OTLP Env Var for Railway Integration

**Status:** Accepted | **Date:** 2026-05-02

**Context:**

The Railway integration endpoint (`POST /api/integrations`) injects OpenTelemetry environment variables into the connected service via the Railway API. The initial implementation used the generic base-URL variable `OTEL_EXPORTER_OTLP_ENDPOINT`. This caused 404 errors because most OTLP SDKs automatically append `/v1/traces` to the base URL when the generic variable is used, resulting in a request to `/api/v1/otlp/v1/traces/v1/traces` (double path suffix).

**Decision:**

The Railway integration injects the following variables:

| Variable | Value injected | Reason |
|---|---|---|
| `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` | `<verumBase>/api/v1/otlp/v1/traces` | Signal-specific variable — SDK uses the URL verbatim without appending `/v1/traces` |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | `http/json` | Verum's OTLP route parses the body with `req.json()`. Binary protobuf (`grpc` / `http/protobuf`) would fail deserialization. |
| `OTEL_EXPORTER_OTLP_HEADERS` | `Authorization=Bearer <api_key>` | Only injected when the user supplies a `verum_api_key`. Matches the `Authorization: Bearer` header that `POST /api/v1/otlp/v1/traces` requires for API key auth. |

`OTEL_EXPORTER_OTLP_ENDPOINT` (the generic base-URL variable) is NOT injected.

**Why:**

- **Signal-specific (`*_TRACES_ENDPOINT`) vs. generic (`OTEL_EXPORTER_OTLP_ENDPOINT`)**: The OpenTelemetry specification defines that signal-specific variables take precedence over the generic one. When the signal-specific variable is set, the SDK sends requests to the exact URL without modification. The generic variable acts as a base URL and SDKs append the signal path (`/v1/traces`) automatically — causing a double-suffix on Verum's pre-suffixed route path.
- **`http/json` protocol**: Verum's OTLP receiver route uses `req.json()` for parsing. Only `http/json` produces a JSON body compatible with this handler. `grpc` and `http/protobuf` produce binary frames that `req.json()` cannot parse.
- **`OTEL_EXPORTER_OTLP_HEADERS` format**: The `key=value` format (no `:`; `=` separator) is the OpenTelemetry standard for header env var values. Multiple headers are comma-separated.

**Trade-off accepted:** Users who configure OTLP outside the Railway integration flow (e.g., manually in other platforms) must use the signal-specific variable `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` and set `OTEL_EXPORTER_OTLP_PROTOCOL=http/json`. The generic `OTEL_EXPORTER_OTLP_ENDPOINT` cannot be used with Verum's endpoint without the protocol override.

**Revisit trigger:** If Verum adds a protobuf/gRPC OTLP receiver in a future phase, `http/protobuf` and `grpc` may be supported alongside `http/json`, and the protocol constraint can be relaxed.

---

### ADR-021: Zod v4 UUID Validation — RFC 4122 Compliant Test Fixtures

**Status:** Active  
**Date:** 2026-05-05

### Context

Zod v4 tightened `z.string().uuid()` to enforce RFC 4122 UUID format strictly:
- 3rd segment's first character (version bits) must be `[1-8]`
- 4th segment's first character (variant bits) must be `[89abAB]`

Zod v3 accepted any hex character in those positions. Test fixtures across the
codebase used placeholder UUIDs like `aaaaaaaa-0000-0000-0000-000000000002`
(version=0, variant=0), which pass Zod v3 but fail Zod v4's regex.

### Decision

1. Keep `z.string().uuid()` in production route schemas unchanged — real UUIDs
   from the database are always valid RFC 4122 UUIDs (generated by PostgreSQL's
   `gen_random_uuid()`).
2. Update all test fixture UUIDs to RFC 4122-compliant format. Pattern used:
   - `xxxxxxxx-0000-0000-0000-*` → `xxxxxxxx-0000-4000-8000-*` (version=4, variant=8)
   - `11111111-1111-1111-1111-*` → `11111111-1111-4111-8111-*`
3. Apply the same fix to Playwright E2E test fixtures.

### Consequences

- All test UUIDs now reflect realistic RFC 4122 v4 UUID format.
- Future test fixtures MUST use valid UUID v4 format (version bit in `[1-8]`,
  variant bit in `[89abAB]`).
- No production code changes required.

**Implemented in:** PR #131

---

_Maintainer: xzawed | Last updated: 2026-05-05 (ADR-021 추가 — Zod v4 UUID 엄격 검증 대응, 테스트 픽스처 RFC 4122 준수 결정 (PR #131))_
