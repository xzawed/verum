# [5] DEPLOY

Stage 5 of The Verum Loop — injecting user-approved `GeneratedAssets` into the connected service via the Verum SDK, starting with a canary traffic split.

> See [docs/LOOP.md §Stage 5](../../../../../docs/LOOP.md#7-stage-5-deploy) for the complete algorithm, I/O contracts, failure modes, and completion criteria.

**Status:** Not implemented. Ships in [Phase 3](../../../../../docs/ROADMAP.md#phase-3-generate--deploy-week-10-13) (F-3.6 through F-3.7).

## Default canary split

New deployments start at 10% canary / 90% baseline.
Auto-rollback triggers if error rate exceeds 5× baseline within the first 100 calls.
