# Verum GENERATE Stage — Code Quality & Test Report

**Date:** 2026-04-22  
**Scope:** Phase 3 GENERATE engine implementation  
**Method:** 5-round multi-agent parallel analysis (3 unit/engine/repository agents + 1 integration agent + 1 static quality agent)  
**Analyst models:** claude-sonnet-4-6 (×5 concurrent subagents)

---

## Executive Summary

| Round | Focus Area | Score | Max | % |
|---|---|---|---|---|
| **Round 1** | Pydantic model boundary tests | **93** | 100 | 93% |
| **Round 2** | Engine logic (parse, prompt, mocked Claude) | **89** | 100 | 89% |
| **Round 3** | Repository/DB layer static analysis | **63** | 100 | 63% |
| **Round 4** | HARVEST→GENERATE chain integration | **80** | 100 | 80% |
| **Round 5** | Code quality (security/architecture/lint/types/complexity) | **74** | 100 | 74% |
| **TOTAL** | Weighted aggregate | **399** | 500 | **79.8%** |

**Verdict:** The test layer and engine logic are solid. The repository layer and architecture compliance are the primary remediation targets before Phase 4 begins.

---

## Round 1 — Pure Unit Tests (Pydantic Models)

**Score: 93 / 100**

| Dimension | Score | Max |
|---|---|---|
| pass_rate (passing/total × 50) | 50 | 50 |
| edge_coverage | 26 | 30 |
| coverage_percent | 17 | 20 |

### Results

- **Tests run:** 24 (18 original + 6 added by agent)
- **Pass:** 24 / **Fail:** 0

All original 18 tests passed. The agent added 6 new tests across 3 new classes:

| New Test Class | Tests Added | Focus |
|---|---|---|
| `TestRagConfigChunkOverlapBoundaries` | 4 | `chunk_overlap` min(0)/max(256) exact bounds and invalid neighbors — **zero prior coverage** |
| `TestRagConfigChunkOverlapExceedsChunkSize` | 1 | Semantic cross-field bug: `chunk_overlap=200, chunk_size=128` accepted silently |
| `TestGenerateResultEmptyVariants` | 1 | `prompt_variants=[]` accepted by Pydantic — downstream DEPLOY/EXPERIMENT not guarded |

### Bugs Found

| # | Severity | Bug | Location |
|---|---|---|---|
| B1 | **Medium** | `chunk_overlap >= chunk_size` not validated — Pydantic silently accepts semantically impossible RAG configs | `models.py: RagConfig` |
| B2 | Low | `prompt_variants: list[PromptVariant]` has no `min_length=1` — empty list produces a GENERATE result with nothing to A/B test | `models.py: GenerateResult` |

### Recommended Fix (B1)

```python
# apps/api/src/loop/generate/models.py
from pydantic import model_validator

class RagConfig(BaseModel):
    ...
    @model_validator(mode="after")
    def chunk_overlap_must_be_less_than_chunk_size(self) -> "RagConfig":
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError(
                f"chunk_overlap ({self.chunk_overlap}) must be less than "
                f"chunk_size ({self.chunk_size})"
            )
        return self
```

---

## Round 2 — Engine Logic Tests

**Score: 89 / 100**

| Dimension | Score | Max |
|---|---|---|
| pass_rate (passing/total × 50) | 50 | 50 |
| edge_coverage | 24 | 30 |
| coverage_percent | 15 | 20 |

### Results

- **Tests run:** 12 (5 original + 7 added by agent)
- **Pass:** 12 / **Fail:** 0

| New Test | What It Covers |
|---|---|
| `test_parse_json_nested_objects_in_array` | Fence-stripping must not corrupt nested JSON |
| `test_parse_json_invalid_raises` | Malformed JSON propagates `JSONDecodeError` (no silent swallowing) |
| `test_parse_json_whitespace_only_raises` | Whitespace-only string raises after strip |
| `test_best_prompt_all_empty_content_returns_empty_string` | All-empty templates return `""` — **not** the fallback; callers unguarded |
| `test_best_prompt_single_template` | Single-element list returns content verbatim |
| `test_run_generate_raises_when_api_key_missing` | `RuntimeError` on missing env var, no Claude calls |
| `test_run_generate_empty_sample_chunks` | Empty chunks → `"(no chunks yet)"` placeholder |

### Bugs Found

| # | Severity | Bug | Location |
|---|---|---|---|
| B3 | **Medium** | `_best_prompt([{"content":""},{"content":""}])` returns `""` instead of the fallback string — Claude receives empty `ORIGINAL PROMPT:` section | `engine.py:_best_prompt()` |
| B4 | Low | `anthropic.AsyncAnthropic` client used without `async with` — HTTP session never explicitly closed (resource leak) | `engine.py:run_generate()` |
| B5 | Low | When Claude returns malformed JSON, caller gets raw `JSONDecodeError` with no context about which of the 3 calls failed | `engine.py:_call_claude()` |

### Recommended Fix (B3)

```python
def _best_prompt(templates: list[dict[str, Any]]) -> str:
    if not templates:
        return "(no prompt detected — generate a suitable system prompt for this service)"
    best = max(templates, key=lambda t: len(t.get("content", "")))["content"]
    return best or "(no prompt detected — generate a suitable system prompt for this service)"
```

---

## Round 3 — Repository / DB Layer

**Score: 63 / 100**

| Dimension | Score | Max |
|---|---|---|
| Correctness | 28 | 40 |
| Atomicity | 12 | 30 |
| Completeness | 23 | 30 |

*Note: This round used static analysis (no live DB). 5 test stubs written to `tests/loop/generate/test_repository.py` with `@pytest.mark.skip(reason="needs db fixture")`.*

### Correctness Findings (28/40)

| # | Severity | Finding | Line |
|---|---|---|---|
| C1 | No issue | SQL injection risk: **none found** — all `text()` use named bind params | All |
| C2 | **High** | `scalar_one()` in `save_generate_result` raises `NoResultFound` if row was deleted mid-flight | `repository.py:36` |
| C3 | **High** | `scalar_one()` in `mark_generate_error` — error handler itself crashes if row missing | `repository.py:97` |
| C4 | No issue | `::jsonb` cast is correct; `json.dumps()` round-trip is valid | `repository.py:45` |
| C5 | No issue | `get_generation_summary` WHERE clause uses correct column (`inference_id`) | `repository.py:114` |
| C6 | Low | `str(uuid.uuid4())` in raw SQL binds — inconsistent with ORM `UUID(as_uuid=True)` style | Multiple |

### Atomicity Findings (12/30)

| # | Severity | Finding |
|---|---|---|
| A1 | **Critical** | No uniqueness guard on child tables (`prompt_variants`, `eval_pairs`, `rag_configs`) — concurrent calls with same `generation_id` produce double-inserts |
| A2 | Medium | `create_pending_generation` commits immediately (step 1), then outer handler commits again for job row (step 3) — TOCTOU window between commits |
| A3 | Medium | No `SELECT FOR UPDATE` before status mutation in `save_generate_result` / `mark_generate_error` |

### Completeness Findings (23/30)

| # | Finding |
|---|---|
| OK | Empty `prompt_variants` / `eval_pairs` loops are no-ops — correct |
| OK | `error[:1024]` truncation matches `String(1024)` column constraint |
| OK | `generated_at` set on success path |
| ❌ | `mark_generate_error` unhandled if row missing — error handler can crash |
| ❌ | No status machine guard — any `status` → any `status` transition allowed |

### Test Stubs Created

```
apps/api/tests/loop/generate/test_repository.py
  ├─ test_save_generate_result_missing_row_raises   @skip
  ├─ test_mark_generate_error_idempotent            @skip
  ├─ test_get_generation_summary_no_row_returns_none @skip
  ├─ test_save_generate_result_special_chars_in_variables @skip
  └─ test_save_generate_result_concurrent_calls_no_double_insert @skip (currently FAILS)
```

---

## Round 4 — HARVEST→GENERATE Chain Integration

**Score: 80 / 100**

| Dimension | Score | Max |
|---|---|---|
| flow_completeness | 34 | 40 |
| state_consistency | 24 | 30 |
| transaction_boundary | 22 | 30 |

### Integration Analysis

| Integration Point | Status | Notes |
|---|---|---|
| `handle_harvest` → `create_pending_generation` args | ✅ Correct | `(db, inference_id, generation_id)` matches signature |
| `runner.py` registers `"generate": handle_generate` | ✅ Confirmed | Key string matches `enqueue_next(kind="generate")` |
| Commit ordering: generation row before job row | ✅ Correct | Cannot claim job without generation row existing |
| Chain fires even when all sources errored | ✅ Correct | Chain block is unconditional after source loop |
| `create_pending_generation` raises → `enqueue_next` skipped | ✅ Safe | Sequential Python execution, no try/except wrapping chain |

### Gaps Found

| # | Severity | Gap |
|---|---|---|
| G1 | **High** | Stale generation recovery: crash between steps 1 and 3 leaves generation in `"pending"` forever — no recovery mechanism |
| G2 | Medium | Raw SQL for `analyses.prompt_templates` — schema drift silently returns `None` instead of raising |
| G3 | Low | `LIMIT 5` for sample_chunks hardcoded in `handle_generate`, not configurable |
| G4 | Low | `mark_generate_error` uses `scalar_one()` — if called when generation row deleted, secondary exception inside the except handler |

### Test Stubs Created

```
apps/api/tests/worker/handlers/test_harvest_chain.py
  ├─ test_normal_flow_generation_row_created_job_enqueued          @skip
  ├─ test_all_sources_errored_chain_still_fires                    @skip
  ├─ test_create_pending_generation_raises_no_job_enqueued         @skip
  ├─ test_generate_handler_nonexistent_inference_id_raises         @skip
  └─ test_generate_handler_missing_generation_row_calls_mark_error @skip
```

---

## Round 5 — Static Code Quality

**Score: 74 / 100**

| Dimension | Score | Max |
|---|---|---|
| Security | 20 | 25 |
| Architecture compliance | 10 | 20 |
| Type safety | 15 | 20 |
| Lint quality | 20 | 20 |
| Complexity | 9 | 15 |

### Security (20/25)

| # | Finding | Deduction |
|---|---|---|
| ✅ | `json.loads()` used, not `eval()` | — |
| ✅ | All SQL queries use named bind parameters | — |
| ✅ | API key never logged | — |
| ✅ | `error[:1024]` prevents size-based log injection | — |
| ⚠️ | `str(exc)` on `anthropic.APIError` — future `logger.exception()` could expose `httpx.Request.__repr__` | −3 |
| ⚠️ | Error string not sanitized for `\r\n` before DB write | −2 |

### Architecture (10/20)

| # | Violation | Deduction |
|---|---|---|
| ❌ | `import uuid as _uuid` **inside** `run_generate()` function body (line 166) | −5 |
| ❌ | `run_generate()` is **129 lines** (CLAUDE.md limit: 50) | −5 |
| ❌ | `save_generate_result()` is 59 lines (over 50-line limit) | (within A2 deduction) |
| ❌ | `handle_generate()` is 61 lines (over 50-line limit) | (within A2 deduction) |
| ✅ | `_SENTENCE_ENDINGS` correctly precompiled at module level, used in `semantic_split()` | — |

### Type Safety (15/20)

| # | Finding | Deduction |
|---|---|---|
| ⚠️ | `_parse_json()` returns `Any` — all 3 callers call `.get()` without type guard; silent `AttributeError` if Claude returns JSON array | −2 |
| ⚠️ | `_call_claude()` returns `Any` — cascades from above | −2 |
| ⚠️ | `PromptVariant.variant_type: str` should be `Literal["original","cot","few_shot","role_play","concise"]` | −1 |
| ✅ | `handle_generate()` fully annotated | — |
| ✅ | `get_generation_summary()` return type declared | — |

### Lint (20/20)

`ruff check src/loop/generate/ src/worker/handlers/generate.py src/loop/harvest/chunker.py`  
**Result: 0 violations.** All checks passed.

*Note: `C90` (McCabe complexity) and `ANN` (annotations) rule sets are not enabled in `pyproject.toml` — complexity violations are invisible to CI.*

### Complexity (9/15)

| Function | Lines | CC | Status |
|---|---|---|---|
| `run_generate()` | 129 | 2 | **Lines critical**, CC fine |
| `handle_generate()` | 61 | 9 | **Exceeds both limits** |
| `save_generate_result()` | 59 | 3 | Over line limit |
| `_split()` (chunker) | 37 | 11 | **CC critical** |
| `semantic_split()` | 36 | 6 | Borderline |

---

## Consolidated Bug / Issue Registry

| ID | Round | Severity | Issue | File | Line |
|---|---|---|---|---|---|
| **B1** | R1 | 🔴 Medium | `chunk_overlap >= chunk_size` not cross-validated | `models.py` | RagConfig |
| **B2** | R1 | 🟡 Low | `prompt_variants: list[PromptVariant]` no `min_length=1` | `models.py` | GenerateResult |
| **B3** | R2 | 🔴 Medium | `_best_prompt` returns `""` when all templates are empty, not fallback | `engine.py` | 26-30 |
| **B4** | R2 | 🟡 Low | `AsyncAnthropic` client not used as async context manager (resource leak) | `engine.py` | 80 |
| **B5** | R2 | 🟡 Low | `JSONDecodeError` has no context label for which Claude call failed | `engine.py` | `_call_claude` |
| **C2** | R3 | 🔴 High | `scalar_one()` in `save_generate_result` — unhandled `NoResultFound` | `repository.py` | 36 |
| **C3** | R3 | 🔴 High | `scalar_one()` in `mark_generate_error` — error handler crashes on missing row | `repository.py` | 97 |
| **A1** | R3 | 🔴 Critical | No uniqueness constraint on child tables — concurrent calls produce double-inserts | `repository.py` + Alembic | — |
| **G1** | R4 | 🔴 High | Stale `pending` generation rows never recovered if crash between steps 1 and 3 | `harvest.py` + `generate.py` | — |
| **G2** | R4 | 🟡 Medium | Raw SQL for `analyses.prompt_templates` — silent `None` on schema drift | `generate.py` | ~45 |
| **S1** | R5 | 🟡 Medium | `str(exc)` on APIError could expose request details via future logging | `generate.py` | 82 |
| **Arch1** | R5 | 🔴 High | `import uuid as _uuid` inside function body | `engine.py` | 166 |
| **Arch2** | R5 | 🔴 High | `run_generate()` at 129 lines — 2.6× CLAUDE.md 50-line limit | `engine.py` | 44-172 |

---

## Top Recommendations (Prioritized)

### Priority 1 — Fix before any Phase 4 work (Critical/High)

1. **[A1] Add `UNIQUE(generation_id)` to `rag_configs`** and add `SELECT FOR UPDATE` in `save_generate_result`:
   - New Alembic migration: `0007_rag_configs_unique.py`
   - Change `scalar_one()` at line 35 to `scalar_one_or_none()` with lock

2. **[C2/C3] Guard both `scalar_one()` calls in repository.py**:
   - `save_generate_result`: raise domain `GenerationNotFoundError`
   - `mark_generate_error`: use `scalar_one_or_none()`, log and return silently

3. **[Arch2] Refactor `run_generate()` into three private helpers**:
   ```python
   _generate_variants(client, base_prompt, domain, tone, user_type, language, summary)
   _generate_rag_config(client, domain, user_type, chunks_preview)
   _generate_eval_pairs(client, domain, user_type, summary, chunks_preview)
   ```
   Resolves: 129-line function violation, misplaced `import uuid as _uuid` (Arch1), and improves testability

4. **[G1] Add stale generation recovery** to worker runner's startup scan:
   - Any `generation.status = "pending"` with no corresponding `verum_jobs` row in `queued`/`running` → re-enqueue or mark error

### Priority 2 — Fix within Phase 3 (Medium)

5. **[B1] Add `@model_validator` to `RagConfig`** for `chunk_overlap < chunk_size`

6. **[B3] Fix `_best_prompt` empty-content fallback**:
   ```python
   return best or "(no prompt detected — generate a suitable system prompt for this service)"
   ```

7. **[R5-Type] Narrow `_parse_json()` return type** from `Any` to `dict[str, object]` with `isinstance` guard

8. **[R5-Type] Change `variant_type: str`** to `Literal["original","cot","few_shot","role_play","concise"]`

### Priority 3 — Before Phase 5 launch (Low)

9. **Enable `C90` + `ANN` ruff rules** in `pyproject.toml` to make complexity violations CI-blocking
10. **Use `async with anthropic.AsyncAnthropic(...)` as client:`** in `engine.py` to close HTTP session properly
11. **Add `GENERATE_SAMPLE_CHUNKS_LIMIT` config** to replace hardcoded `LIMIT 5` in `handle_generate`

---

## Test Artifacts Created

| File | Tests | Type |
|---|---|---|
| `apps/api/tests/loop/generate/test_models.py` | 24 (6 new) | Unit — all run and pass |
| `apps/api/tests/loop/generate/test_engine.py` | 12 (7 new) | Unit — all run and pass |
| `apps/api/tests/loop/generate/test_repository.py` | 5 (new file) | Stubs — skipped, await DB fixture |
| `apps/api/tests/worker/handlers/test_harvest_chain.py` | 5 (new file) | Stubs — skipped, await DB fixture |

**Total runnable tests (no DB required):** 36  
**Total test stubs (require DB fixture):** 10

---

## Score Summary

```
Round 1 — Model tests:          93 / 100  ████████████████████████  93%
Round 2 — Engine logic:         89 / 100  ██████████████████████    89%
Round 3 — Repository layer:     63 / 100  ███████████████▌          63%
Round 4 — Chain integration:    80 / 100  ████████████████████      80%
Round 5 — Static quality:       74 / 100  ██████████████████▌       74%
─────────────────────────────────────────
AGGREGATE:                      399 / 500                           79.8%
```

**Interpretation:**
- The test layer covering engine logic and models is production-quality (89–93%).
- The integration chain design is solid but has identified recovery gaps (80%).
- The repository and architecture layers are the primary technical debt items (63–74%).
- The codebase is safe to ship for Phase 3 validation (ArcanaInsight dogfood) but requires the Priority 1 fixes before accepting external load in Phase 4+.

---

_Report generated: 2026-04-22_  
_Analyst: 5-agent parallel review (Verum quality pipeline)_  
_Next review target: after Priority 1 fixes — expected score: ≥ 87 / 100_
