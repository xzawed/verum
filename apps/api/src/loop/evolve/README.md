# [8] EVOLVE

Stage 8 of The Verum Loop — promoting the winning variant to 100% traffic, archiving losers, and optionally triggering the next ANALYZE cycle.

> See [docs/LOOP.md §Stage 8](../../../../../docs/LOOP.md#10-stage-8-evolve) for the complete algorithm, I/O contracts, failure modes, and completion criteria.

**Status:** Not implemented. Ships in [Phase 4](../../../../../docs/ROADMAP.md#phase-4-observe--experiment--evolve-week-14-18) (F-4.8 through F-4.9).

## The closed loop

After EVOLVE completes, the next ANALYZE job is enqueued (`next_cycle_triggered = true`). This closes The Verum Loop — the system continuously learns and improves without manual intervention.
