---
type: decisions
authority: tier-2
canonical-for: [adr-index, product-scope-decisions, superseded-decisions]
last-updated: 2026-04-24
status: active
---

# Verum — Architecture Decision Records (Index)

> **Claude instructions:** This file is the index and product-scope decision log.
> Full ADR text (rationale, trade-offs, revisit triggers) lives in [ARCHITECTURE.md §7](ARCHITECTURE.md#7-architecture-decision-records).
> Before proposing a new dependency or structural change, verify it does not conflict with an ADR below.
> To record a new decision: add a one-line entry here AND write the full ADR in ARCHITECTURE.md §7.
> Authority: CLAUDE.md > ARCHITECTURE.md §7 (full text) > this file (index).

---

## Active ADRs

| ADR | Topic | Decision | Full text |
|---|---|---|---|
| ADR-001 | Vector storage | pgvector only — no Pinecone, Weaviate, Qdrant, Chroma | [ARCHITECTURE.md §ADR-001](ARCHITECTURE.md#adr-001-pgvector-only--no-external-vector-db) |
| ADR-002 | LLM framework | No LangChain / LlamaIndex in any package | [ARCHITECTURE.md §ADR-002](ARCHITECTURE.md#adr-002-no-langchain--llamaindex-in-any-package) |
| ~~ADR-003~~ | ~~Web framework~~ | ~~FastAPI + Uvicorn~~ — **Superseded by ADR-009** (2026-04-20) | [ARCHITECTURE.md §ADR-003](ARCHITECTURE.md#adr-003-fastapi--uvicorn) |
| ADR-004 | DB access | SQLAlchemy 2 async + Alembic, no raw SQL | [ARCHITECTURE.md §ADR-004](ARCHITECTURE.md#adr-004-sqlalchemy-2-async--alembic--no-raw-sql) |
| ADR-005 | Python style | `async def` for all I/O; no sync in `apps/` or `packages/sdk-python/` | [ARCHITECTURE.md §ADR-005](ARCHITECTURE.md#adr-005-async-first-python) |
| ADR-006 | Dashboard | Next.js 16 App Router + React 19 + Tailwind CSS v4 + Zustand | [ARCHITECTURE.md §ADR-006](ARCHITECTURE.md#adr-006-nextjs-16-app-router--react-19) |
| ADR-007 | Embedding dims | Never hardcode — store per-collection in `harvest_sources.embedding_dim` | [ARCHITECTURE.md §ADR-007](ARCHITECTURE.md#adr-007-never-hardcode-embedding-dimensions) |
| ADR-008 | Loop directory | `apps/api/src/loop/{8 stages}/` is sacred — CLAUDE.md update required before adding/removing a stage | [ARCHITECTURE.md §ADR-008](ARCHITECTURE.md#adr-008-appsapisrclop-directory-structure-is-sacred) |
| ADR-009 | Runtime architecture | Single container: Node.js PID 1 + Python worker child + Postgres job queue. Supersedes ADR-003. | [ARCHITECTURE.md §ADR-009](ARCHITECTURE.md#adr-009-single-container--nodejs-pid-1--python-worker-child--postgres-job-queue) |
| ADR-010 | next build compatibility | All external clients (OpenAI, DB pool, etc.) must be lazy-initialized inside a getter function, never at module scope | [ARCHITECTURE.md §ADR-010](ARCHITECTURE.md#adr-010-lazy-initialization-for-next-build-compatibility) |
| ADR-011 | Codecov uploader | `codecov/codecov-action` pinned to **v5**. v4 bundled uploader suffered a shasum/GPG regression (2026-04-26); v5 uses `codecov-cli` and avoids the issue. `fail_ci_if_error` remains `false` until green baseline confirmed, then set to `true`. | [ARCHITECTURE.md §ADR-011](ARCHITECTURE.md#adr-011-codecov-action-pinned-to-v5) |
| ADR-012 | Integration test via prod-image compose + mock provider stack | Full Verum Loop (ANALYZE→EVOLVE) validated against the same `Dockerfile` used in Railway. All external APIs redirected to a FastAPI mock stack. 5+2 env-gated hooks in production code; business logic (`apps/api/src/loop/**`) untouched. `VERUM_TEST_MODE=1` exposes `api_key` in DEPLOY job result for fake-arcana. Nightly + workflow_dispatch CI; informational until 2-week stability baseline. | [INTEGRATION.md](INTEGRATION.md) |
| ADR-013 | SQLAlchemy `text()` PostgreSQL cast syntax | `text()` 쿼리에서 `:param::type` 캐스트 금지. `CAST(:param AS type)` 만 허용. | [ARCHITECTURE.md §ADR-013](ARCHITECTURE.md#adr-013-sqlalchemy-text--postgresql-cast-syntax) |

---

## Product-Scope Decisions

These are product-level choices that are not implementation ADRs but define the boundaries of what Verum is.

| Decision | Summary | Date |
|---|---|---|
| Verum ≠ Verum AI | Verum is a distinct project from verumai.com. All landing pages must include `> Not affiliated with Verum AI Platform (verumai.com).` | 2026-04-19 |
| Dogfood first | Every Phase has an ArcanaInsight completion gate. A phase is not done until ArcanaInsight works. "It should work in theory" does not count. | 2026-04-19 |
| Dual-mode, feature-parity | Features are never split between open-source and cloud. The only cloud differentiator is hosting, scaling, and managed operations. | 2026-04-19 |
| Direct library usage only | The loop's 8 stages use `openai`, `anthropic`, `httpx`, `pgvector`, etc. directly. No LangChain/LlamaIndex intermediary. | 2026-04-19 |
| Sacred loop directory | `apps/api/src/loop/` must always contain exactly the 8 stage directories. Refactoring this structure requires CLAUDE.md update first. | 2026-04-19 |
| GENERATE outputs are proposals | Everything GENERATE produces is in `"pending_approval"` state. DEPLOY may not touch production without explicit user approval. | 2026-04-19 |
| Static analysis only for ANALYZE | ANALYZE is purely static — AST parsing, no service execution. Running the target service is permitted only in OBSERVE. | 2026-04-19 |

---

## How to Add a New ADR

1. Choose the next ADR number (ADR-009, ADR-010, ...).
2. Add a one-line entry in the **Active ADRs** table above.
3. Add the full ADR in [ARCHITECTURE.md §7](ARCHITECTURE.md#7-architecture-decision-records) with:
   - **Status** (Accepted / Proposed / Superseded)
   - **Date**
   - **Decision** (what was decided)
   - **Why** (the rationale — prevents re-litigating later)
   - **Trade-off accepted**
   - **Revisit trigger** (if applicable)
4. Reference the ADR ID in relevant commit messages and PR descriptions.

---

## Superseded Decisions

| Decision | Superseded by | Date |
|---|---|---|
| RAG = Operational Knowledge Only | CLAUDE.md §🔁 The Verum Loop / Stage [3] HARVEST | 2026-04-19 |
| ADR-003: FastAPI + Uvicorn | ADR-009: Single Container pivot | 2026-04-20 |

**Supersession detail:** A prior approved spec (`2026-04-19-verum-rag-scope-realignment`) defined Verum's RAG as indexing *operational LLM knowledge only* (system prompts, personas, business rules) and explicitly excluded domain content (tarot meanings, legal texts, etc.).

CLAUDE.md's HARVEST stage definition (§🔁 Stage [3]) supersedes this. HARVEST's algorithm explicitly crawls domain content: tarot interpretation sites, StackOverflow, legal databases, Wikipedia — whatever is authoritative for the inferred domain. This is not a reversal of the RAG architecture but an expansion of *what counts as relevant knowledge*: the loop's purpose is to understand a service's actual domain, which requires domain knowledge, not just operational configuration.

The old spec's metadata convention (`kind`, `version`, `service`, `active`, `tags` on indexed documents) remains a useful convention and can be adopted in the `knowledge_chunks.metadata` JSONB column.

---

_Maintainer: xzawed | Last updated: 2026-04-22_
