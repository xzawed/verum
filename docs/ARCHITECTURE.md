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
              │   • knowledge_chunks        │
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
│           │   └── db/         # Drizzle ORM client + introspected schema
│           └── middleware.ts   # Auth.js v5 route protection
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
| `source_url` | `TEXT` | |
| `chunk_count` | `INT` | |
| `collection_name` | `TEXT` | pgvector collection |
| `embedding_model` | `TEXT` | |
| `embedding_dim` | `INT` | persisted here; never hardcoded downstream |
| `harvested_at` | `TIMESTAMPTZ` | |

### `knowledge_chunks`

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

### `evolutions`

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` PK | |
| `experiment_id` | `UUID` FK → experiments | |
| `promoted_deployment_id` | `UUID` | |
| `archived_deployment_ids` | `UUID[]` | |
| `next_cycle_triggered` | `BOOL` | |
| `evolved_at` | `TIMESTAMPTZ` | |

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
| POST | `/v1/analyze` | Start analysis job for a repo | ✅ |
| GET | `/v1/analyze/{analysis_id}` | Get analysis result | ✅ |
| GET | `/v1/repos/{repo_id}/analyses` | List analyses for a repo | ✅ |

### [2] INFER

| Method | Path | Description | Status |
|---|---|---|---|
| POST | `/v1/infer` | Run inference on an analysis | ✅ |
| GET | `/v1/infer/{inference_id}` | Get inference result | ✅ |
| PATCH | `/v1/infer/{inference_id}/confirm` | User confirms or overrides inference | ✅ |

### [3] HARVEST

| Method | Path | Description | Status |
|---|---|---|---|
| POST | `/v1/harvest/propose` | LLM proposes sources; returns list for user approval | ✅ |
| POST | `/v1/harvest/start` | Start crawl with approved sources | ✅ |
| GET | `/v1/harvest/{harvest_id}` | Get harvest status + result | ✅ |
| POST | `/v1/retrieve` | Hybrid search over knowledge_chunks | ✅ |

### [4] GENERATE

| Method | Path | Description | Status |
|---|---|---|---|
| POST | `/v1/generate` | Generate assets from harvest | ✅ |
| GET | `/v1/generate/{asset_id}` | Get generated assets | ✅ |
| PATCH | `/v1/generate/{asset_id}/approve` | User approves generated assets | ✅ |

### [5] DEPLOY

| Method | Path | Description | Status |
|---|---|---|---|
| POST | `/v1/deploy` | Deploy approved assets | ✅ |
| GET | `/v1/deployments/{deployment_id}` | Get deployment status | ✅ |
| PATCH | `/v1/deployments/{deployment_id}/traffic` | Adjust traffic split | ✅ |
| POST | `/v1/deployments/{deployment_id}/rollback` | Rollback to baseline | ✅ |

### [6] OBSERVE

| Method | Path | Description | Status |
|---|---|---|---|
| POST | `/v1/traces` | Ingest trace (SDK → API) | 🔲 |
| GET | `/v1/traces` | List traces (paginated, filterable) | 🔲 |
| GET | `/v1/traces/{trace_id}` | Get trace + spans | 🔲 |
| GET | `/v1/metrics` | Aggregated cost/latency/quality metrics | 🔲 |

### [7] EXPERIMENT

| Method | Path | Description | Status |
|---|---|---|---|
| POST | `/v1/experiments` | Create experiment across deployments | 🔲 |
| GET | `/v1/experiments/{experiment_id}` | Get experiment result | 🔲 |

### [8] EVOLVE

| Method | Path | Description | Status |
|---|---|---|---|
| POST | `/v1/evolve` | Trigger evolution from concluded experiment | 🔲 |
| GET | `/v1/evolutions/{evolution_id}` | Get evolution result | 🔲 |

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
import { Verum } from "@verum/sdk";

const verum = new Verum({ apiKey: "...", projectId: "..." });

const response = await verum.chat({ model: "grok-2-1212", messages: [...], deploymentId: "..." });
const chunks = await verum.retrieve({ query: "...", collection: "arcana-tarot-knowledge", topK: 5 });
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

**Why:** Verum supports multiple embedding models (OpenAI = 1536, BGE-M3 = 1024). Hardcoding breaks when the user switches models. Dimension is persisted at collection creation and propagated from `harvest_sources`.

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

_Maintainer: xzawed | Last updated: 2026-04-25_
