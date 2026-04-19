---
type: architecture
authority: tier-2
canonical-for: [file-tree, schemas, api-contracts, sdk-surface, adrs, infra]
last-updated: 2026-04-19
status: active
---

# Verum — Architecture

> **Claude instructions:** This file owns the file tree, database schemas, API contracts, SDK surface, and ADR full text.
> Section 2 (Repository Layout) MUST mirror CLAUDE.md §📁 exactly — verify on every change.
> When deciding where a new file belongs, consult §2 before creating anything.
> Authority: CLAUDE.md > this file > LOOP.md for stage details.

---

## 1. System Overview

```
                        ┌─────────────────────────────────────────┐
                        │              Verum Platform              │
                        │                                          │
  ┌──────────┐  GitHub  │  ┌─────────────────────────────────┐    │
  │   Repo   │─OAuth──→ │  │      The Verum Loop Engine       │    │
  └──────────┘          │  │  [1]ANALYZE → [2]INFER →        │    │
                        │  │  [3]HARVEST → [4]GENERATE →     │    │
  ┌──────────┐  SDK     │  │  [5]DEPLOY → [6]OBSERVE →      │    │
  │Connected │←────────→│  │  [7]EXPERIMENT → [8]EVOLVE      │    │
  │ Service  │          │  └────────────┬────────────────────┘    │
  └──────────┘          │               │                          │
                        │  ┌────────────▼───────────────────┐     │
  ┌──────────┐  Browser │  │       FastAPI (apps/api/)       │     │
  │Dashboard │←────────→│  │    REST API + WebSocket         │     │
  │(Next.js) │          │  └────────────┬───────────────────┘     │
  └──────────┘          │               │                          │
                        │  ┌────────────▼───────────────────┐     │
                        │  │    PostgreSQL 16 + pgvector     │     │
                        │  │    tsvector (hybrid search)     │     │
                        │  └────────────────────────────────┘     │
                        └─────────────────────────────────────────┘
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
│   ├── GLOSSARY.md             # Vocabulary (tier-3)
│   └── guides/                 # Phase 5+ end-user docs
├── apps/
│   ├── api/                    # FastAPI backend
│   │   ├── src/
│   │   │   ├── main.py         # FastAPI app entry + /health
│   │   │   ├── loop/           # The Verum Loop — SACRED (ADR-008)
│   │   │   │   ├── analyze/    # [1] Repo static analysis
│   │   │   │   ├── infer/      # [2] Service intent inference
│   │   │   │   ├── harvest/    # [3] Domain knowledge crawling
│   │   │   │   ├── generate/   # [4] Asset auto-generation
│   │   │   │   ├── deploy/     # [5] SDK injection
│   │   │   │   ├── observe/    # [6] Runtime tracing
│   │   │   │   ├── experiment/ # [7] A/B testing
│   │   │   │   └── evolve/     # [8] Winner promotion
│   │   │   ├── integrations/   # GitHub OAuth, webhook handlers
│   │   │   └── db/             # SQLAlchemy models, session factory
│   │   ├── tests/
│   │   ├── alembic/
│   │   ├── pyproject.toml
│   │   └── Dockerfile
│   └── dashboard/              # Next.js 16 App Router
│       ├── src/app/
│       ├── src/components/
│       ├── package.json
│       └── Dockerfile
├── packages/
│   ├── sdk-python/             # pip install verum
│   │   ├── src/verum/
│   │   └── pyproject.toml
│   └── sdk-typescript/         # npm install @verum/sdk
│       ├── src/
│       └── package.json
├── examples/
│   └── arcana-integration/     # ArcanaInsight dogfood (first real user)
├── docker-compose.yml
├── Makefile
├── CLAUDE.md                   # Tier-1 authority — xzawed-only edits
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
| [3] HARVEST | `apps/api/src/loop/harvest/` | `httpx`, `trafilatura`, `playwright` |
| [4] GENERATE | `apps/api/src/loop/generate/` | `openai` / `anthropic`, `pgvector` |
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

### `generated_assets`

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` PK | |
| `harvest_source_id` | `UUID` FK → harvest_sources | |
| `prompt_variants` | `JSONB` | list of PromptVariant |
| `rag_config` | `JSONB` | chunking strategy + retrieval params |
| `eval_dataset` | `JSONB` | list of {query, expected_answer} |
| `dashboard_profile` | `JSONB` | metric weights |
| `status` | `TEXT` | `"pending_approval"` / `"approved"` / `"archived"` |
| `created_at` | `TIMESTAMPTZ` | |

### `deployments`

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` PK | |
| `asset_id` | `UUID` FK → generated_assets | |
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

Base path: `/v1`. All endpoints return JSON. Authentication: Bearer token (Phase 1+).

### Health

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Returns `{"status": "ok", "version": "...", "db": "connected"}` |

### [1] ANALYZE

| Method | Path | Description |
|---|---|---|
| POST | `/v1/analyze` | Start analysis job for a repo |
| GET | `/v1/analyze/{analysis_id}` | Get analysis result |
| GET | `/v1/repos/{repo_id}/analyses` | List analyses for a repo |

### [2] INFER

| Method | Path | Description |
|---|---|---|
| POST | `/v1/infer` | Run inference on an analysis |
| GET | `/v1/infer/{inference_id}` | Get inference result |
| PATCH | `/v1/infer/{inference_id}/confirm` | User confirms or overrides inference |

### [3] HARVEST

| Method | Path | Description |
|---|---|---|
| POST | `/v1/harvest/propose` | LLM proposes sources; returns list for user approval |
| POST | `/v1/harvest/start` | Start crawl with approved sources |
| GET | `/v1/harvest/{harvest_id}` | Get harvest status + result |
| POST | `/v1/retrieve` | Hybrid search over knowledge_chunks |

### [4] GENERATE

| Method | Path | Description |
|---|---|---|
| POST | `/v1/generate` | Generate assets from harvest |
| GET | `/v1/generate/{asset_id}` | Get generated assets |
| PATCH | `/v1/generate/{asset_id}/approve` | User approves generated assets |

### [5] DEPLOY

| Method | Path | Description |
|---|---|---|
| POST | `/v1/deploy` | Deploy approved assets |
| GET | `/v1/deployments/{deployment_id}` | Get deployment status |
| PATCH | `/v1/deployments/{deployment_id}/traffic` | Adjust traffic split |
| POST | `/v1/deployments/{deployment_id}/rollback` | Rollback to baseline |

### [6] OBSERVE

| Method | Path | Description |
|---|---|---|
| POST | `/v1/traces` | Ingest trace (SDK → API) |
| GET | `/v1/traces` | List traces (paginated, filterable) |
| GET | `/v1/traces/{trace_id}` | Get trace + spans |
| GET | `/v1/metrics` | Aggregated cost/latency/quality metrics |

### [7] EXPERIMENT

| Method | Path | Description |
|---|---|---|
| POST | `/v1/experiments` | Create experiment across deployments |
| GET | `/v1/experiments/{experiment_id}` | Get experiment result |

### [8] EVOLVE

| Method | Path | Description |
|---|---|---|
| POST | `/v1/evolve` | Trigger evolution from concluded experiment |
| GET | `/v1/evolutions/{evolution_id}` | Get evolution result |

---

## 6. SDK Surface

Both SDKs expose identical high-level APIs. Internals differ by language.

### Python SDK (`verum`)

```python
import verum

verum.configure(api_key="...", project_id="...")

response = await verum.chat(
    model="grok-2-1212",
    messages=[...],
    deployment_id="...",
)

chunks = await verum.retrieve(
    query="어떤 카드가 나왔나요?",
    collection="arcana-tarot-knowledge",
    top_k=5,
)

await verum.feedback(trace_id="...", score=1)
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

**Status:** Accepted | **Date:** 2026-04-19

**Decision:** API is FastAPI + Uvicorn. Django, Flask, and Litestar are prohibited.

**Why:** FastAPI is async-first (matches ADR-005), has native Pydantic v2 integration, and auto-generates OpenAPI docs. Django's ORM conflicts with SQLAlchemy; Flask lacks async.

---

### ADR-004: SQLAlchemy 2 Async + Alembic — No Raw SQL

**Status:** Accepted | **Date:** 2026-04-19

**Decision:** All database access goes through SQLAlchemy 2 async session. All schema changes go through Alembic. Raw SQL strings in application code are prohibited.

**Why:** SQLAlchemy 2 async integrates cleanly with FastAPI. Alembic provides reproducible schema history for self-hosted deployments. Raw SQL bypasses type safety and migration tracking.

---

### ADR-005: Async-first Python

**Status:** Accepted | **Date:** 2026-04-19

**Decision:** All I/O-bound functions in `apps/api/` and `packages/sdk-python/` must be `async def`. Synchronous I/O is prohibited in these packages.

**Why:** Blocking I/O stalls FastAPI's event loop. HARVEST (crawler) and OBSERVE (SDK instrumentation) are heavily I/O-bound.

---

### ADR-006: Next.js 16 App Router + React 19

**Status:** Accepted | **Date:** 2026-04-19

**Decision:** Dashboard is Next.js 16 App Router, React 19, TypeScript strict, Tailwind CSS v4, Recharts, Zustand, NextAuth.

**Why:** Server components reduce bundle size. React 19 server actions simplify forms. NextAuth covers GitHub OAuth natively (required for ANALYZE repo connection).

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

## 8. Infrastructure & Deployment

### Docker Compose (Self-Hosted)

Three services: `api` (FastAPI), `dashboard` (Next.js), `db` (PostgreSQL 16 + pgvector).

Self-hosting is a first-class requirement. `docker compose up` must bring up the full stack.

### Railway (Initial Cloud)

- API: Railway service pulling from `apps/api/Dockerfile`
- Dashboard: Railway service pulling from `apps/dashboard/Dockerfile`
- DB: Railway PostgreSQL plugin with pgvector extension enabled

### Image Size Constraint

Final Docker images must be under 1GB. Use multistage builds.

### CI/CD

`.github/workflows/ci.yml`:
- `ruff`, `pylint`, `bandit`, `mypy` on Python
- `tsc --noEmit`, `eslint` on TypeScript
- `pytest` with coverage (Phase 2+: ≥ 80%)
- Merge blocked on failure

---

_Maintainer: xzawed | Last updated: 2026-04-19_
