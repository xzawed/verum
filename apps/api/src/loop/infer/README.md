# [2] INFER

Stage 2 of The Verum Loop — feeding ANALYZE output to an LLM to produce a structured `ServiceInference` (domain, tone, language, user type).

> See [docs/LOOP.md §Stage 2](../../../../../docs/LOOP.md#4-stage-2-infer) for the complete algorithm, I/O contracts, failure modes, and completion criteria.

**Status:** Not implemented. Ships in [Phase 2](../../../../../docs/ROADMAP.md#phase-2-infer--harvest-week-6-9) (F-2.1 through F-2.3).

## Primary dependency

- `anthropic` — Claude Sonnet 4.6+ is used for structured reasoning (INFER requires multi-step inference)
