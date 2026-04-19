# [4] GENERATE

Stage 4 of The Verum Loop — automatically producing prompt variants, RAG configs, eval datasets, and dashboard profiles from the HARVEST knowledge base.

> See [docs/LOOP.md §Stage 4](../../../../../docs/LOOP.md#6-stage-4-generate) for the complete algorithm, I/O contracts, failure modes, and completion criteria.

**Status:** Not implemented. Ships in [Phase 3](../../../../../docs/ROADMAP.md#phase-3-generate--deploy-week-10-13) (F-3.1 through F-3.5).

## Key principle

All GENERATE outputs are **proposals** — they are persisted with `status = "pending_approval"`.
DEPLOY may not inject anything into a connected service without explicit user approval.
See [CLAUDE.md §⚠️ item 10](../../../../../CLAUDE.md).
