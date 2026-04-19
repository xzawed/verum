# [3] HARVEST

Stage 3 of The Verum Loop — crawling and indexing domain knowledge based on the `ServiceInference` result.

> See [docs/LOOP.md §Stage 3](../../../../../docs/LOOP.md#5-stage-3-harvest) for the complete algorithm, I/O contracts, failure modes, and completion criteria.

**Status:** Not implemented. Ships in [Phase 2](../../../../../docs/ROADMAP.md#phase-2-infer--harvest-week-6-9) (F-2.4 through F-2.11).

## Scope

HARVEST collects **domain content** (tarot meanings, legal texts, technical docs, etc.) as determined by the INFER result. This is intentional — see [docs/DECISIONS.md §Superseded](../../../../../docs/DECISIONS.md#superseded-decisions) for why the earlier "operational knowledge only" scope was expanded.

## Primary dependencies

- `httpx` — async HTTP crawling
- `trafilatura` — HTML → clean text extraction
- `playwright` — JS-rendered page crawling
- `pgvector` — vector storage (via PostgreSQL)
