# [1] ANALYZE

Stage 1 of The Verum Loop — static analysis of a connected Repo to extract LLM call sites and prompt patterns.

> See [docs/LOOP.md §Stage 1](../../../../../docs/LOOP.md#3-stage-1-analyze) for the complete algorithm, I/O contracts, failure modes, and completion criteria.

**Status:** Not implemented. Ships in [Phase 1](../../../../../docs/ROADMAP.md#phase-1-analyze-week-3-5) (F-1.2 through F-1.8).

## Key principle

ANALYZE is **static only** — it must never require the target service to run.
If an analysis approach requires executing the service, it belongs in [6] OBSERVE, not here.
See [CLAUDE.md §⚠️ item 9](../../../../../CLAUDE.md).

## Primary dependencies

- `ast` (Python stdlib) — Python AST parsing
- `libcst` — Python CST for preserving formatting
- `tree-sitter` — TypeScript/JavaScript AST parsing
