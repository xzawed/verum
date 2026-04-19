---
type: glossary
authority: tier-3
canonical-for: [vocabulary]
last-updated: 2026-04-19
status: active
---

# Verum Glossary

> **Claude instructions:** This file prevents vocabulary drift. When writing code or documentation, use
> the exact terms defined here. If a term here conflicts with how a concept is described in CLAUDE.md,
> CLAUDE.md wins. Do not add synonyms or alternate forms — pick the canonical term and use it everywhere.
> Authority: CLAUDE.md > this file.

---

## Terms (Alphabetical)

**[N] STAGE_NAME** — The canonical format for referring to a loop stage. Always uppercase, always square-bracketed number. Examples: `[1] ANALYZE`, `[3] HARVEST`, `[8] EVOLVE`. Never abbreviate (not "Analyze", not "ANLZ"). Never reorder. See [LOOP.md](LOOP.md) for definitions.

**ANALYZE** — Stage [1] of The Verum Loop. Static analysis of a connected Repo to extract LLM call sites and prompt patterns. Does not require the target service to run. See [LOOP.md §Stage 1](LOOP.md#3-stage-1-analyze).

**Auto-evolution** — The outcome of a complete OBSERVE → EXPERIMENT → EVOLVE cycle in which the winning prompt or RAG config is promoted without human intervention. This is Verum's core value proposition. See [LOOP.md §Stage 8](LOOP.md#10-stage-8-evolve).

**Connected service** — A user's application that has integrated the Verum SDK (`verum.chat()`, `verum.retrieve()`). The generic term used in non-CLAUDE.md documentation to avoid ArcanaInsight-specific language. ArcanaInsight is the reference connected service.

**DEPLOY** — Stage [5] of The Verum Loop. Injecting user-approved GENERATE outputs into a connected service via the SDK, starting with a canary split. See [LOOP.md §Stage 5](LOOP.md#7-stage-5-deploy).

**Dogfood / Dogfooding** — Applying Verum to one of xzawed's own services before any external release. ArcanaInsight is the primary dogfood target. A phase is not complete until the dogfood gate passes.

**EVOLVE** — Stage [8] of The Verum Loop. Promoting the winning variant from a concluded experiment to 100% traffic and archiving losers. See [LOOP.md §Stage 8](LOOP.md#10-stage-8-evolve).

**EXPERIMENT** — Stage [7] of The Verum Loop. Running a Bayesian A/B test across multiple deployed variants and determining a winner with statistical confidence. See [LOOP.md §Stage 7](LOOP.md#9-stage-7-experiment).

**F-{phase}.{n}** — Deliverable ID format used in ROADMAP.md. Example: `F-2.4` = Phase 2, deliverable 4. Use these IDs in commit message scopes and PR descriptions.

**GENERATE** — Stage [4] of The Verum Loop. Automatically producing prompt variants, RAG configs, eval datasets, and dashboard profiles from the HARVEST knowledge base. All outputs are proposals in `"pending_approval"` state. See [LOOP.md §Stage 4](LOOP.md#6-stage-4-generate).

**HARVEST** — Stage [3] of The Verum Loop. Crawling and indexing domain knowledge based on the INFER result. Includes domain content (tarot meanings, legal texts, etc.) — not limited to operational knowledge. See [LOOP.md §Stage 3](LOOP.md#5-stage-3-harvest).

**INFER** — Stage [2] of The Verum Loop. Feeding ANALYZE output to an LLM to produce a structured `ServiceInference` (domain, tone, language, user type). See [LOOP.md §Stage 2](LOOP.md#4-stage-2-infer).

**Knowledge chunks** — The atomic units of indexed knowledge in pgvector. Each chunk has a `content` text field, an `embedding` vector column, and a `tsv` tsvector column for hybrid search. Produced by HARVEST, consumed by GENERATE and the `POST /v1/retrieve` endpoint.

**Loop** — Shorthand for The Verum Loop: the 8-stage cycle ANALYZE → INFER → HARVEST → GENERATE → DEPLOY → OBSERVE → EXPERIMENT → EVOLVE. Always capitalized when referring to Verum's loop. See [CLAUDE.md §🔁](../CLAUDE.md) and [LOOP.md](LOOP.md).

**OBSERVE** — Stage [6] of The Verum Loop. Collecting OpenTelemetry-compatible traces and spans from the connected service's `verum.chat()` calls. See [LOOP.md §Stage 6](LOOP.md#8-stage-6-observe).

**Operational knowledge** — *Deprecated as a standalone concept.* Previously used to distinguish system prompts, personas, and business rules from domain content. Since HARVEST explicitly collects both, this term no longer marks a boundary. Use "knowledge chunks" for indexed content and refer to the chunk's `metadata.kind` field for fine-grained categorization.

**Phase** — A roadmap time period (Phase 0 through Phase 5). Phase ≠ Stage. A Phase is a development timeline milestone; a Stage is a position in The Verum Loop. Multiple stages ship within one phase. See [ROADMAP.md](ROADMAP.md).

**pgvector** — The PostgreSQL extension used for all vector storage in Verum. No other vector database is permitted (ADR-001). The `knowledge_chunks.embedding` column is a `vector(N)` type where `N` is read from `harvest_sources.embedding_dim` — never hardcoded (ADR-007).

**RAG** — Retrieval-Augmented Generation. In Verum's context: the HARVEST pipeline produces `knowledge_chunks` stored in pgvector + tsvector; the `POST /v1/retrieve` endpoint performs hybrid BM25 + vector search; the GENERATE stage uses retrieved chunks to build RAG configs. Verum implements its own RAG — no LangChain/LlamaIndex dependency (ADR-002).

**Repo** — A Git repository connected to Verum via GitHub OAuth. The starting point of The Verum Loop's ANALYZE stage.

**Repo-first** — The principle that Verum's analysis begins with a connected Repo, not with runtime instrumentation. ANALYZE is purely static. See [CLAUDE.md §핵심 가치](../CLAUDE.md).

**Stage** — A position in The Verum Loop ([1] through [8]). Stage ≠ Phase. A stage maps to a directory in `apps/api/src/loop/` and is implemented across one or more roadmap phases.

**The Verum Loop** — See [CLAUDE.md §🔁](../CLAUDE.md) for the authoritative definition. See [LOOP.md](LOOP.md) for implementation detail.

**Verum** — This project: an open-source AI service auto-optimization platform built by xzawed. Full name is "Verum" — never "Verum AI" (see below).

**Verum AI** — A different company at verumai.com. Not affiliated with this project. Never use "Verum AI" to refer to this project. All landing pages must include the brand-safety disclaimer. See [CLAUDE.md §⚠️ 하지 말아야 할 것 item 8](../CLAUDE.md).

---

_Maintainer: xzawed | Last updated: 2026-04-19_
