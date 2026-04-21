---
type: roadmap
authority: tier-2
canonical-for: [phase-timing, completion-gates, deliverable-ids]
last-updated: 2026-04-22
status: active
---

# Verum — 6-Month Roadmap

> **Claude instructions:** This file owns phase timing, binary completion gates, and F-{phase}.{n} deliverable IDs.
> Use F-IDs in commit messages (`feat(analyze): F-1.3 add tree-sitter JS detection`) and PR descriptions.
> Phase completion gates are binary — a phase is not done until its gate passes.
> The decision guide at the bottom mirrors CLAUDE.md §🧭 — when in doubt, apply it.
> Authority: CLAUDE.md > this file > LOOP.md for stage algorithm detail.

---

## Phase 0: Foundation (Week 1–2)

**Goal:** Project scaffolding. Deploy a "Hello World" that satisfies the CI and health check gate.

**Completion gate:** `curl https://verum-api.up.railway.app/health` returns HTTP 200 with `{"status": "ok"}`.

### Deliverables

| ID | Deliverable | Status |
|---|---|---|
| F-0.1 | Monorepo structure initialized (`apps/`, `packages/`, `docs/`, `.github/`) | ✅ |
| F-0.2 | GitHub repository created (`github.com/xzawed/verum`) | ✅ |
| F-0.3 | MIT license added | ✅ |
| F-0.4 | English README (`README.md`) with brand-safety statement | ✅ |
| F-0.5 | Korean README (`README.ko.md`) | ✅ |
| F-0.6 | Docker Compose: `api` + `db` (PostgreSQL 16 + pgvector) + `dashboard` services | ✅ |
| F-0.7 | GitHub Actions CI: `ruff`, `pylint`, `bandit`, `mypy`, `tsc --noEmit`, `pytest` | 🚧 |
| F-0.8 | Railway deployment pipeline configured | ✅ |
| F-0.9 | `GET /health` endpoint returning `{"status": "ok", "version": "...", "db": "connected"}` | ✅ |

### ArcanaInsight Validation

No ArcanaInsight integration yet. This phase is infrastructure only.

### Non-goals for Phase 0

Do not implement any loop stage logic. Infrastructure only.

---

## Phase 1: ANALYZE (Week 3–5)

**Goal:** Loop [1] ANALYZE — receive a connected Repo and extract all LLM call patterns.

**Completion gate:** ArcanaInsight's Grok call sites are all auto-detected and their prompts accurately extracted.

### Deliverables

| ID | Deliverable | Status |
|---|---|---|
| F-1.1 | GitHub OAuth integration (user grants repo access) | ✅ |
| F-1.2 | Repo clone to isolated temp environment | ✅ |
| F-1.3 | Python AST-based LLM call detection (`openai`, `anthropic`, `xai_grok`, `google.generativeai`) | ✅ |
| F-1.4 | TypeScript/JavaScript `tree-sitter` based LLM call detection | 🚧 |
| F-1.5 | Prompt string extraction (string literals, f-strings, template literals) | ✅ |
| F-1.6 | Model + parameter extraction (`model`, `temperature`, `max_tokens`) | ✅ |
| F-1.7 | Analysis result stored as structured JSON (`AnalysisResult` Pydantic model) | ✅ |
| F-1.8 | `POST /v1/analyze` + `GET /v1/analyze/{id}` endpoints | 🚧 note: job-queue based, not REST |
| F-1.9 | Dashboard: repo connection UI + analysis result viewer | ✅ |

### ArcanaInsight Validation

ArcanaInsight uses `xai_grok` SDK in Python. All Grok `chat.completions.create()` calls must appear in `call_sites` with correct `file_path`, `line`, and extracted prompt.

### Metrics to Measure at Phase 1 Completion

- Count of LLM call sites detected in ArcanaInsight (target: 100% recall vs manual count)
- False-positive rate (non-LLM calls flagged as LLM calls): target < 1%
- Analysis wall-clock time for ArcanaInsight repo (target: < 60 seconds)

---

## Phase 2: INFER + HARVEST (Week 6–9)

**Goal:** Loop [2] INFER + [3] HARVEST — understand the service's intent, then auto-collect domain knowledge.

**Completion gate:** ArcanaInsight → domain inferred as `"divination/tarot"` with confidence ≥ 0.80; 1,000+ knowledge chunks harvested and searchable via `POST /v1/retrieve`.

### Deliverables

| ID | Deliverable | Status |
|---|---|---|
| F-2.1 | INFER engine: prompts + README → `ServiceInference` JSON via Claude Sonnet 4.6+ | ✅ |
| F-2.2 | Domain classification taxonomy (initial 20 categories) | ✅ |
| F-2.3 | `POST /v1/infer` + `GET /v1/infer/{id}` + `PATCH /v1/infer/{id}/confirm` endpoints | 🚧 note: job-queue based |
| F-2.4 | HARVEST engine: domain-aware crawling strategy with LLM-proposed sources | ✅ |
| F-2.5 | Source proposal + user approval flow (dashboard UI) | ✅ auto-approved; manual toggle deferred |
| F-2.6 | Crawling: `httpx` (static) + `playwright` (JS-rendered) | 🚧 httpx done; playwright Phase 3 |
| F-2.7 | Text extraction with `trafilatura` | ✅ |
| F-2.8 | Recursive chunking (mandatory) + Semantic chunking (Phase 2) | 🚧 recursive done; semantic Phase 3 |
| F-2.9 | Embedding pipeline: OpenAI `text-embedding-3-small` (default) | ✅ |
| F-2.10 | pgvector storage + `tsvector` column for hybrid search | ✅ |
| F-2.11 | `POST /v1/harvest/propose` + `POST /v1/harvest/start` + `POST /v1/retrieve` | 🚧 note: job-queue based |
| F-2.12 | Dashboard: INFER result visualization + HARVEST progress + chunk search UI | ✅ |
| F-2.13 | Auto-chain ANALYZE → INFER → HARVEST on repo registration (no manual steps) | ✅ |
| F-2.14 | Real-time progress polling (3s) on repo detail page | ✅ |

### ArcanaInsight Validation

- INFER output: `{"domain": "divination/tarot", "tone": "mystical", "language": "ko", "user_type": "consumer"}`
- HARVEST: 1,000+ chunks from tarot knowledge sources, stored in collection `arcana-tarot-knowledge`
- Retrieval: `POST /v1/retrieve` returns relevant chunks for "어떤 카드가 나왔나요?"

### Metrics to Measure at Phase 2 Completion

- INFER confidence on ArcanaInsight (target: ≥ 0.80)
- Chunk count in `arcana-tarot-knowledge` (target: ≥ 1,000)
- Retrieval P95 latency (target: < 200ms)
- Manual quality sample: 10 random chunks rated for relevance (target: ≥ 8/10)

---

## Phase 3: GENERATE + DEPLOY (Week 10–13)

**Goal:** Loop [4] GENERATE + [5] DEPLOY — auto-build assets and inject them into ArcanaInsight.

**Completion gate:** ArcanaInsight's tarot consultation runs on a Verum-generated prompt and retrieves from the Verum-built RAG. Verified by xzawed in production.

### Deliverables

| ID | Deliverable | Status |
|---|---|---|
| F-3.1 | Prompt variant generator: 5 patterns (original, CoT, few-shot, role-play, concise) | 🔲 |
| F-3.2 | RAG config auto-selection (chunking strategy + `top_k` + hybrid weights) | 🔲 |
| F-3.3 | Eval dataset generation: 30–50 query/answer pairs via LLM | 🔲 |
| F-3.4 | Dashboard metric profile auto-selection (consumer vs developer vs enterprise) | 🔲 |
| F-3.5 | `POST /v1/generate` + `GET /v1/generate/{id}` + `PATCH /v1/generate/{id}/approve` | 🔲 |
| F-3.6 | DEPLOY engine: canary at 10% traffic, SDK-side routing | 🔲 |
| F-3.7 | `POST /v1/deploy` + traffic split endpoints + rollback | 🔲 |
| F-3.8 | Python SDK `verum.chat()` + `verum.retrieve()` + `verum.feedback()` | 🔲 |
| F-3.9 | TypeScript SDK `@verum/sdk` — full parity with Python SDK | 🔲 |
| F-3.10 | **ArcanaInsight SDK integration** — tarot endpoint using `verum.chat()` and `verum.retrieve()` | 🔲 |

### ArcanaInsight Validation

ArcanaInsight's tarot reading endpoint must:
1. Call `verum.chat()` (wrapping the Grok SDK call)
2. Call `verum.retrieve()` to pull tarot knowledge context before the LLM call
3. The canary (10% traffic) must use a Verum-generated Chain-of-Thought prompt variant

### Metrics to Measure at Phase 3 Completion

- Prompt variants generated for ArcanaInsight tarot (target: 5)
- Eval dataset pairs (target: ≥ 30)
- SDK overhead on ArcanaInsight P95 response time (target: < 10ms added)
- TypeScript SDK test coverage (target: ≥ 80%)

---

## Phase 4: OBSERVE + EXPERIMENT + EVOLVE (Week 14–18)

**Goal:** Loop [6] OBSERVE + [7] EXPERIMENT + [8] EVOLVE — close the loop. ArcanaInsight's prompt improves automatically.

**Completion gate:** ArcanaInsight's prompt is auto-improved at least once with a measurable metric gain, with no manual intervention from xzawed.

### Deliverables

| ID | Deliverable | Status |
|---|---|---|
| F-4.1 | OpenTelemetry-compatible trace/span ingestion (`POST /v1/traces`) | 🔲 |
| F-4.2 | Cost calculation: token count × pricing table (OpenAI, Anthropic, xAI) | 🔲 |
| F-4.3 | Dashboard: trace list + span waterfall view + cost/latency metrics | 🔲 |
| F-4.4 | User feedback collection: `verum.feedback(trace_id, score)` | 🔲 |
| F-4.5 | A/B test engine: traffic split + Bayesian stopping criterion | 🔲 |
| F-4.6 | RAGAS integration: faithfulness, answer_relevancy, context_precision | 🔲 |
| F-4.7 | LLM-as-Judge evaluation (async job per trace) | 🔲 |
| F-4.8 | Auto-winner selection: weighted score (satisfaction + RAGAS + cost) at confidence ≥ 0.95 | 🔲 |
| F-4.9 | EVOLVE: promote winner to 100% traffic, archive losers | 🔲 |
| F-4.10 | Dashboard: experiment view + evolution history | 🔲 |
| F-4.11 | **ArcanaInsight auto-evolution** — at least 1 prompt improvement cycle completed | 🔲 |

### ArcanaInsight Validation

A complete OBSERVE → EXPERIMENT → EVOLVE cycle on ArcanaInsight tarot:
1. Both baseline and CoT variant accumulate ≥ 100 calls each
2. Bayesian test concludes with confidence ≥ 0.95
3. Winner is promoted to 100% traffic automatically
4. xzawed confirms metric improvement in `docs/WEEKLY.md`

### Metrics to Measure at Phase 4 Completion

- ArcanaInsight traces/week in Verum dashboard
- RAGAS faithfulness score before/after EVOLVE (target: improvement ≥ 0.05)
- Experiment convergence time (target: < 2 weeks)
- Verum's own weekly cost (target: < $20/week)

---

## Phase 5: Launch (Week 19–24)

**Goal:** Open-source release. First external users.

**Completion gate:** GitHub stars ≥ 100; ≥ 10 non-xzawed users with a connected Repo.

### Deliverables

| ID | Deliverable | Status |
|---|---|---|
| F-5.1 | English documentation site live (`docs.verum.dev`) | 🔲 |
| F-5.2 | Quickstart guide (connect Repo → full loop in < 30 minutes) | 🔲 |
| F-5.3 | API reference | 🔲 |
| F-5.4 | Python SDK reference | 🔲 |
| F-5.5 | TypeScript SDK reference | 🔲 |
| F-5.6 | Self-hosting guide (`docker compose up` walkthrough) | 🔲 |
| F-5.7 | ArcanaInsight case study (auto-optimization in production) | 🔲 |
| F-5.8 | "How Verum Works" blog posts: 3–5 articles (dev.to, Medium, velog) | 🔲 |
| F-5.9 | Hacker News / Reddit r/MachineLearning launch post | 🔲 |
| F-5.10 | Langfuse vs Verum honest comparison document | 🔲 |
| F-5.11 | Demo video: ArcanaInsight auto-optimization real-time (3–5 minutes, Loom) | 🔲 |
| F-5.12 | Demo environment live (`demo.verum.dev`) with pre-populated data | 🔲 |
| F-5.13 | Cloud SaaS MVP open (`verum.dev`) with GitHub OAuth onboarding | 🔲 |
| F-5.14 | "Not affiliated with Verum AI Platform (verumai.com)" statement on all landing pages | 🔲 |

---

## Decision Guide for Prioritization

When choosing between tasks within a phase, apply this order:

1. **The Verum Loop에서 더 앞 단계인 쪽 우선** — earlier stages unblock later ones; always clear the blocker first.
2. **Phase 0–1: simple implementations only** — no premature abstraction.
3. **Phase 2+: consider scalability** when choosing between approaches.
4. **Abstract at 3, not before** — three identical implementations justify an abstraction; two do not.
5. **ArcanaInsight dogfood wins ties** — if two tasks are equal priority, pick the one that advances ArcanaInsight integration.

---

_Maintainer: xzawed | Last updated: 2026-04-22_
