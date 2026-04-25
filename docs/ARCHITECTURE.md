---
type: architecture
authority: tier-2
canonical-for: [file-tree, schemas, api-contracts, sdk-surface, adrs, infra]
last-updated: 2026-04-22
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
| [1] ANALYZE | `apps/api/src/loop/analyze/` | `ast`, `libcst`, `tree-sitter` |
| [2] INFER | `apps/api/src/loop/infer/` | `anthropic` (Claude Sonnet 4.6+) |
| [3] HARVEST | `apps/api/src/loop/harvest/` | `httpx`, `trafilatura`, `playwright` (opt-in, soft import) |
| [4] GENERATE | `apps/api/src/loop/generate/` | `anthropic` (Claude Sonnet 4.6+), `pgvector` |
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
| `analysis_id` | `UUID` FK → analyses | |
| `domain` | `TEXT` | |
| `subdomain` | `TEXT` | nullable |
| `tone` | `TEXT` | |
| `language` | `TEXT` | BCP-47 |
| `user_type` | `TEXT` | |
| `confidence` | `FLOAT` | |
| `raw_llm_response` | `TEXT` | |
| `inferred_at` | `TIMESTAMPTZ` | |

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
| `harvest_source_id` | `UUID` FK → harvest_sources | |
| `content` | `TEXT` | raw chunk text |
| `embedding` | `vector(N)` | N from `harvest_sources.embedding_dim` |
| `tsv` | `TSVECTOR` | for BM25 hybrid search |
| `metadata` | `JSONB` | `{"domain": ..., "source_url": ...}` |
| `created_at` | `TIMESTAMPTZ` | |

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
| `generation_id` | `UUID` FK → generations | |
| `status` | `TEXT` | `"shadow"` / `"canary"` / `"full"` / `"rolled_back"` / `"archived"` |
| `traffic_split` | `JSONB` | `{"baseline": 0.9, "variant": 0.1}` |
| `deployed_at` | `TIMESTAMPTZ` | |
| `archived_at` | `TIMESTAMPTZ` | nullable |

### `traces`

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` PK | |
| `deployment_id` | `UUID` FK → deployments | nullable |
| `name` | `TEXT` | |
| `start_time` | `TIMESTAMPTZ` | |
| `end_time` | `TIMESTAMPTZ` | |
| `status` | `TEXT` | `"ok"` / `"error"` |
| `metadata` | `JSONB` | |

### `spans`

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` PK | |
| `trace_id` | `UUID` FK → traces | |
| `parent_span_id` | `UUID` | nullable for root span |
| `name` | `TEXT` | |
| `model` | `TEXT` | |
| `input_tokens` | `INT` | |
| `output_tokens` | `INT` | |
| `cost_usd` | `NUMERIC(10,6)` | |
| `latency_ms` | `INT` | |
| `start_time` | `TIMESTAMPTZ` | |
| `end_time` | `TIMESTAMPTZ` | |
| `attributes` | `JSONB` | |

### `experiments`

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` PK | |
| `deployment_ids` | `UUID[]` | variants under test |
| `evaluation_metric` | `TEXT` | |
| `stopping_rule` | `TEXT` | `"bayesian"` / `"fixed_horizon"` |
| `winner_deployment_id` | `UUID` | nullable until decided |
| `confidence` | `FLOAT` | |
| `status` | `TEXT` | `"running"` / `"concluded"` / `"inconclusive"` |
| `started_at` | `TIMESTAMPTZ` | |
| `concluded_at` | `TIMESTAMPTZ` | nullable |

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
| GET | `/api/v1/repos/{repo_id}/analyses` | List analyses for a repo | ✅ |

### [2] INFER

| Method | Path | Description | Status |
|---|---|---|---|
| POST | `/api/v1/infer` | Run inference on an analysis | ✅ |
| GET | `/api/v1/infer/{inference_id}` | Get inference result | ✅ |
| PATCH | `/api/v1/infer/{inference_id}/confirm` | User confirms or overrides inference | ✅ |

### [3] HARVEST

| Method | Path | Description | Status |
|---|---|---|---|
| POST | `/api/v1/harvest/propose` | LLM proposes sources; returns list for user approval | ✅ |
| POST | `/api/v1/harvest/start` | Start crawl with approved sources | ✅ |
| GET | `/api/v1/harvest/{harvest_id}` | Get harvest status + result | ✅ |
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
| GET | `/api/v1/deployments/{deployment_id}` | Get deployment status | ✅ |
| PATCH | `/api/v1/deployments/{deployment_id}/traffic` | Adjust traffic split | ✅ |
| POST | `/api/v1/deployments/{deployment_id}/rollback` | Rollback to baseline | ✅ |

### [6] OBSERVE

| Method | Path | Description | Status |
|---|---|---|---|
| POST | `/api/v1/traces` | Ingest trace (SDK → API) | ✅ |
| GET | `/api/v1/traces` | List traces (paginated, filterable) | ✅ |
| GET | `/api/v1/traces/{trace_id}` | Get trace + spans | ✅ |
| GET | `/api/v1/metrics` | Aggregated cost/latency/quality metrics | ✅ |

### [7] EXPERIMENT

| Method | Path | Description | Status |
|---|---|---|---|
| POST | `/api/v1/experiments` | Create experiment across deployments | ✅ |
| GET | `/api/v1/experiments/{experiment_id}` | Get experiment result | ✅ |

### [8] EVOLVE

EVOLVE is triggered automatically as a `verum_jobs` worker job when an experiment converges (no direct HTTP trigger endpoint). Winner promotion, traffic update, and experiment archive are written back to `deployments` and `experiments` tables by the Python worker.

| Method | Path | Description | Status |
|---|---|---|---|
| GET | `/api/v1/experiments/{experiment_id}` | Check experiment status + winner (shared with [7]) | ✅ |

---

## 6. SDK Surface

Both SDKs expose identical high-level APIs. Internals differ by language.

### Python SDK (`verum`)

```python
import verum

# Reads VERUM_API_URL and VERUM_API_KEY from environment
client = verum.Client()

# Route LLM call through Verum (returns modified messages with variant prompt)
routed = await client.chat(
    messages=[...],
    deployment_id="...",
    provider="grok",
    model="grok-2-1212",
)
# Pass routed["messages"] to the actual LLM SDK

# Hybrid RAG retrieval from harvested knowledge
chunks = await client.retrieve(
    query="어떤 카드가 나왔나요?",
    collection_name="arcana-tarot-knowledge",
    top_k=5,
)

await client.feedback(trace_id="...", score=1)
```

### TypeScript SDK (`@verum/sdk`)

```typescript
import { VerumClient } from "@verum/sdk";

const verum = new VerumClient({ apiUrl: "https://verum.dev", apiKey: "..." });

const response = await verum.chat({ model: "grok-2-1212", messages: [...], deploymentId: "..." });
const chunks = await verum.retrieve({ query: "...", collectionName: "arcana-tarot-knowledge", topK: 5 });
```

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

_Maintainer: xzawed | Last updated: 2026-04-25 (ADR-016/017 추가 — Non-invasive SDK, fail-open 5-layer safety net)_
