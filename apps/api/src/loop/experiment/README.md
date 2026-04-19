# [7] EXPERIMENT

Stage 7 of The Verum Loop — running a Bayesian A/B test across multiple deployed variants and determining a winner with statistical confidence ≥ 0.95.

> See [docs/LOOP.md §Stage 7](../../../../../docs/LOOP.md#9-stage-7-experiment) for the complete algorithm, I/O contracts, failure modes, and completion criteria.

**Status:** Not implemented. Ships in [Phase 4](../../../../../docs/ROADMAP.md#phase-4-observe--experiment--evolve-week-14-18) (F-4.5).

## Primary dependency

- `scipy` — Bayesian posterior computation for the stopping criterion
