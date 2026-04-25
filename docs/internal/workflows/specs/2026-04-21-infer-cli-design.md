# INFER Engine Bug Fix + CLI Design

**Date**: 2026-04-21  
**Phase**: Phase 2 — INFER  
**Scope**: Approach B — bug fix + CLI + end-to-end validation

---

## Goal

Fix the `analysis_id` bug in `engine.py` and add a CLI entry point so INFER can be run and verified locally without a job queue, mirroring the ANALYZE CLI pattern.

---

## Changes

### 1. `src/loop/infer/engine.py`

**Bug**: Line 139 sets `analysis_id=result.repo_id` (uses repo UUID instead of analysis UUID).  
**Fix**: Add `analysis_id: uuid.UUID` parameter to `run_infer()` and use it directly.

```python
async def run_infer(result: AnalysisResult, *, analysis_id: uuid.UUID) -> ServiceInference:
```

The `ServiceInference` constructor call changes from:
```python
# Before (broken)
analysis_id=result.repo_id,  # will be replaced by caller with actual analysis_id
```
to:
```python
# After (correct)
analysis_id=analysis_id,
```

### 2. `src/worker/handlers/infer.py`

Update call site to pass `analysis_id` explicitly. Remove the `model_copy` workaround:

```python
result = await run_infer(ar, analysis_id=analysis_id)
# Remove: result = result.model_copy(update={"analysis_id": analysis_id})
```

### 3. `src/loop/infer/cli.py` (new file)

CLI entry point: `python -m src.loop.infer.cli --analysis-id <uuid>`

**Flow:**
1. Parse `--analysis-id` argument (UUID)
2. Open async DB session via `AsyncSessionLocal`
3. Query `Analysis` row by ID; exit with error if not found
4. Reconstruct `AnalysisResult` from DB columns
5. Call `run_infer(ar, analysis_id=analysis_id)`
6. Print `result.model_dump(mode="json")` as indented JSON to stdout

**Dependencies required:**
- `DATABASE_URL` env var (Postgres connection)
- `ANTHROPIC_API_KEY` env var (Claude API)

**DB writes:** None — CLI is read + validate only. Job queue handler owns persistence.

### 4. `Makefile`

Replace the `loop-infer` stub with the real command:

```makefile
loop-infer:
	cd apps/api && python -m src.loop.infer.cli --analysis-id $(ANALYSIS_ID)
```

Usage: `make loop-infer ANALYSIS_ID=<uuid-from-loop-analyze-output>`

---

## Verification

Run end-to-end on ArcanaInsight:

```bash
# Step 1: get an analysis_id from ANALYZE output
make loop-analyze REPO=https://github.com/xzawed/ArcanaInsight

# Step 2: pass the repo_id (used as analysis_id in CLI) to INFER
make loop-infer ANALYSIS_ID=<uuid>
```

Expected result confirms Phase 2 INFER completion criteria:
```json
{
  "domain": "divination/tarot",
  "tone": "mystical",
  "language": "ko",
  "user_type": "consumer",
  "confidence": 0.85
}
```

---

## Out of Scope

- HARVEST CLI (follow-up task)
- DB constraint migrations
- Embedder retry/backoff logic
- Integration tests for full pipeline
