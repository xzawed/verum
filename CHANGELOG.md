# Changelog

All notable changes to Verum are documented in this file.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).  
Versioning: phases are used as milestones until the first stable release (`1.0.0`).

---

## [Unreleased]

### Added
- **Non-invasive integration Phase 0** (OTLP env-only, zero code changes): set `OTEL_EXPORTER_OTLP_ENDPOINT` + `OTEL_EXPORTER_OTLP_HEADERS` to stream openinference spans to `POST /api/v1/otlp/v1/traces`
- **Non-invasive integration Phase 1** (`import verum.openai` / `import "@verum/sdk/openai"`): 1-line monkey-patch activates A/B routing + prompt injection via `extra_headers={"x-verum-deployment": ...}` with 5-layer fail-open safety net (200ms timeout / circuit breaker / 60s fresh cache / 24h stale cache / passthrough). See [ADR-016](docs/ARCHITECTURE.md), [ADR-017](docs/ARCHITECTURE.md)
- **ActivationCard** (`GET /api/v1/activation/[repoId]`): replaces `SdkPrSection`; shows INFER domain, GENERATE variants, HARVEST chunk count, and surfaces two integration mode buttons (observe / bidirectional)
- **OTLP HTTP receiver** (`POST /api/v1/otlp/v1/traces`): accepts openinference protobuf spans; no auth required for ingest

### Changed
- `GENERATE_MAX_TOKENS` default raised from `2048` → `4096` to prevent truncation of multi-variant Korean prompt responses
- `parse_json_response()` now attempts best-effort truncation repair (`_repair_truncated_json`) on `JSONDecodeError` before re-raising
- `verum.Client.chat()` now emits `DeprecationWarning` in v1.x. Migrate via [docs/MIGRATION_v0_to_v1.md](docs/MIGRATION_v0_to_v1.md)

### Removed
- `apps/dashboard/src/lib/sdk-pr/verum-inline.ts` — hardcoded 70-line `VERUM_CLIENT_SOURCE` string (replaced by `pip install verum` / `npm install @verum/sdk` instruction in PR template)
- `apps/dashboard/src/components/repos/SdkPrSection.tsx` — replaced by `ActivationCard`

---

Next: Phase 4-B — EXPERIMENT + EVOLVE (F-4.5, F-4.6, F-4.8)

### Planned
- Bayesian A/B test engine with traffic splitting
- RAGAS integration (faithfulness, answer_relevancy, context_precision)
- Weighted-sum winner selection and automatic promotion (EVOLVE)
- `docs/METHODOLOGY.md` §7, §8, §9 completed alongside implementation

---

## [Phase 4-A] — 2026-04-23 — OBSERVE

### Added
- **LLM-as-Judge scoring** (`judge` worker job): async Claude-based quality scoring for every trace; `judge_score` stored in `traces`, full prompt/response in `judge_prompts` for auditability
- **Trace + span ingestion** (`POST /api/v1/traces`): SDK → API trace pipeline with cost calculation via `model_pricing` table
- **Cost calculation**: token-based cost using seeded `model_pricing` table (6 models: grok-2-1212, grok-2-mini, claude-sonnet-4-6, claude-haiku-4-5, gpt-4o, gpt-4o-mini)
- **User feedback** (`POST /api/v1/feedback`, `client.feedback()`): thumbs up/down on any trace
- **Dashboard OBSERVE section** (`ObserveSection.tsx`): metric cards, 7/30-day Recharts bar chart, paginated trace table
- **SpanWaterfall** slide-over panel: span detail + cost breakdown + Judge score + reasoning
- **`client.record()`** method in Python SDK: records trace after LLM call, returns `trace_id`
- **`GET /api/v1/metrics`**: daily aggregation (cost, call count, P95 latency, avg judge score)
- **`GET /api/v1/traces`** + **`GET /api/v1/traces/[id]`**: paginated list and detail with full ownership verification
- **Alembic migration 0009**: `model_pricing`, `traces`, `spans`, `judge_prompts` tables
- **`docs/METHODOLOGY.md`**: algorithm and prompt reference document covering GENERATE + OBSERVE stages
- **`docs/STATUS.md`**: session-start reference document (loop stage status, file map, API index)

### Security
- IDOR fix on `GET /api/v1/traces/[id]`: added JOIN chain `traces → deployments → generations → inferences → analyses → repos → owner_user_id`
- SQL injection fix in daily metrics: `INTERVAL` now parameterized as `(INTERVAL '1 day' * :days)` instead of f-string interpolation
- `insertTrace` wrapped in `db.transaction()` for atomic trace + span + job insertion

---

## [Phase 3] — 2026-04-22 — GENERATE + DEPLOY

### Added
- **GENERATE engine** (`apps/api/src/loop/generate/engine.py`): three Claude Sonnet calls produce prompt variants (5 patterns), RAG config, and eval pairs
- **5 prompt variant types**: `original`, `cot`, `few_shot`, `role_play`, `concise`
- **RAG config auto-selection**: chunking strategy, chunk_size, top_k, hybrid_alpha recommended by LLM
- **Eval dataset generation**: 20 Q&A pairs via LLM (`eval_pairs` table)
- **Dashboard metric profile auto-selection**: consumer / developer / enterprise profiles
- **`POST /v1/generate`** + **`GET /v1/generate/[id]`** + **`PATCH /v1/generate/[id]/approve`** endpoints
- **DEPLOY engine**: canary at 10% traffic, SDK-side routing
- **`POST /v1/deploy`** + traffic split + rollback endpoints
- **Python SDK** (`packages/sdk-python`): `verum.chat()`, `verum.retrieve()`, `verum.feedback()`
- **TypeScript SDK** (`packages/sdk-typescript`): full parity with Python SDK
- **ArcanaInsight integration example** (`examples/arcana-integration/`)
- **Alembic migrations 0005–0008**: `generations`, `prompt_variants`, `rag_configs`, `eval_pairs`, `deployments`, `pending` generation status

---

## [Phase 2] — 2026-04-21 — INFER + HARVEST

### Added
- **INFER engine**: Claude Sonnet classifies domain, tone, language, user_type from extracted prompts + README
- **20-category domain taxonomy** for service classification
- **`POST /v1/infer`** + polling + `PATCH /v1/infer/[id]/confirm` endpoints
- **HARVEST engine**: domain-aware web crawling with LLM-proposed sources
- **Crawler**: `httpx` (static) + `trafilatura` text extraction
- **Recursive + semantic chunking** strategies
- **Embedding pipeline**: OpenAI `text-embedding-3-small` → pgvector storage
- **Hybrid search**: `tsvector` column + pgvector for `POST /v1/retrieve`
- **Auto-chain**: ANALYZE → INFER → HARVEST triggered on repo registration
- **Dashboard**: INFER result viewer + HARVEST progress + chunk search UI + 3s polling
- **Alembic migrations 0003–0004**: `inferences`, `harvest_sources`, `chunks`, `collections`, `verum_jobs`, `worker_heartbeat`

---

## [Phase 1] — 2026-04-20 — ANALYZE

### Added
- **Python AST-based LLM call detection**: `openai`, `anthropic`, `xai_grok`, `google.generativeai`
- **TypeScript/JavaScript tree-sitter based detection**
- **Prompt string extraction**: string literals, f-strings, template literals
- **Model + parameter extraction**: `model`, `temperature`, `max_tokens`
- **GitHub OAuth integration**: repo access with `public_repo` scope
- **Repo clone** to isolated temp environment
- **`POST /v1/analyze`** + **`GET /v1/analyze/[id]`** endpoints
- **Dashboard**: repo connection UI + analysis result viewer
- **Architecture pivot** (ADR-009): FastAPI removed; Node.js PID 1 + Python worker child process
- **Alembic migrations 0001–0002**: `users`, `repos`, `analyses`

---

## [Phase 0] — 2026-04-19 — Foundation

### Added
- Monorepo structure: `apps/`, `packages/`, `docs/`, `.github/`
- GitHub repository (`github.com/xzawed/verum`)
- MIT license
- English README + Korean README
- Docker Compose: `api` + `db` (PostgreSQL 16 + pgvector) + `dashboard` services
- Single-image Dockerfile: Node.js PID 1 + Python worker subprocess
- GitHub Actions CI: ruff, pylint, bandit, mypy, tsc, pytest
- Railway deployment pipeline
- `GET /health` endpoint returning `{"status": "ok", "version": "...", "db": "connected"}`
