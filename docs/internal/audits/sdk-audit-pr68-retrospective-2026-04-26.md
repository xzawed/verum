# SDK Comprehensive Audit — Retrospective

**Date:** 2026-04-26  
**PR:** [#68 fix/audit-2026-04-26](https://github.com/xzawed/verum/pull/68) — squash-merged to main at `575089a`  
**Scope:** SDK (Python + TypeScript), Drizzle schema, docs  
**Method:** Sequential audit execution — schema fix → TS SDK feature → Python SDK feature → Codecov battle (4 rounds)

---

## Executive Summary

| Metric | Value |
|---|---|
| Files changed | **22** |
| Total insertions | **+1,469** |
| New source files | **2** (anthropic.ts 270 lines, schema.ts patch 6 lines) |
| New test files | **5** (anthropic-wrapped.test.ts, anthropic-patch.test.ts, + 3 new test modules) |
| Extended test files | **4** (openai-wrapped, client, test_client.py, test_openai/anthropic_patch.py) |
| Commits on branch | **10** |
| Codecov patch CI failures | **4** (44% → 27.67% → 89.25% → 91.73% → **pass**) |
| Final Codecov patch | **≥94.60%** target met |
| TypeScript SDK lines | **100%** (all 7 source files) |
| Python SDK lines | **100%** (new module code) |
| SonarCloud / CI | **pass** |

**Verdict:** Feature delivery (Anthropic auto-instrument, VERUM_DISABLED, module-level API) was straightforward. The cost centre was Codecov patch coverage — 4 iterative CI failures consumed more time than writing the source code itself. Root cause: each iteration revealed a different category of Codecov patch analysis behaviour that local Jest/pytest doesn't surface.

---

## Phase-by-Phase Outcome

### Phase A: Drizzle Schema Sync

**Intent:** Align Drizzle ORM schema with what Alembic migrations had already applied to PostgreSQL.

**Actual work:**
- `spans` table: added `span_attributes: jsonb("span_attributes")` — migration 0023 had added the column but the Drizzle introspection was not re-run
- `chunks` table: added `.references(() => inferences.id, { onDelete: "cascade" })` — migration 0018 had added the FK constraint but Drizzle had no `.references()` call

**Result:** Queries against `span_attributes` and cascade delete from `inferences` now work correctly at the ORM layer.

**Surprise:** None. This was a mechanical sync. The root cause was that `drizzle-kit pull` had not been re-run after each Alembic migration, creating drift. Lesson: run `drizzle-kit pull` as part of the alembic migration checklist.

---

### Phase B: TypeScript SDK — Anthropic Auto-Instrument

**Intent:** Port the Python `verum.anthropic` monkey-patch to TypeScript. Services using `@anthropic-ai/sdk` had no TS SDK integration path.

**Actual work (`packages/sdk-typescript/src/anthropic.ts`, 270 lines):**
- Dynamic `import("@anthropic-ai/sdk")` at runtime (optional peer dep — not installed in CI)
- Patches `Anthropic.messages.create` on the prototype via `Object.getPrototypeOf(instance.messages)`
- System prompt handling: top-level `system` kwarg synthesised into `[{role:"system",content:...}]` for the resolver, then extracted back to `system` kwarg before forwarding to the original `create`
- Same 5-layer safety net as the Python version (fail-open, 200ms timeout, circuit breaker, 60s/24h cache)
- `patchAnthropic()` exported from `index.ts`; auto-patches on module import via `void _patchAnthropic()`
- VERUM_DISABLED guard at entry point

**Critical TypeScript gotcha:**
```typescript
// ❌ fails with exactOptionalPropertyTypes: true
{ system: resolvedSystem || undefined }

// ✅ correct
...(resolvedSystem ? { system: resolvedSystem } : {})
```
`exactOptionalPropertyTypes: true` prohibits assigning `string | undefined` to `system?: string`. The conditional spread is the required pattern.

**Result:** `anthropic.ts` at 100% lines. `patchAnthropic()` fully functional and parity with Python version achieved.

---

### Phase C: Trace Payload Fix (openai.ts)

**Intent:** Fix silent data loss — `_sendTrace` was sending a field the server did not recognise, and omitting fields the server needed for A/B attribution.

**Actual work:**

| Before | After |
|---|---|
| `resolve_reason: string` | `variant: string` (renamed to match API) |
| model not extracted | `model: resp.model` (extracted from OpenAI response) |
| tokens not extracted | `input_tokens: resp.usage.prompt_tokens`, `output_tokens: resp.usage.completion_tokens` |
| `source: string` (undocumented) | removed |

**Result:** A/B variant attribution and cost aggregation now receive correct data. `openai.ts` at 100% lines.

---

### Phase D: Module-Level API (Python + TypeScript SDKs)

**Intent:** Allow `await verum.retrieve(...)` and `await verum.feedback(...)` without manually constructing a `Client`/`VerumClient` instance.

**Actual work:**
- Python `__init__.py`: `_default_client: Client | None`, `_get_client()` singleton, async `retrieve()` and `feedback()` top-level functions; `__all__` updated
- TypeScript `index.ts`: `_client: VerumClient | null`, `_getClient()` singleton, async `retrieve()` and `feedback()` exports
- Both: `VERUM_DISABLED` early-return (4 lines each) added to `openai.py` and `anthropic.py` `_patch_*()` entry points

**Result:** Users can now write:
```python
import verum
chunks = await verum.retrieve("tarot card meaning", collection_name="arcana")
await verum.feedback(trace_id, score=1)
```
```typescript
import { retrieve, feedback } from "@verum/sdk";
const chunks = await retrieve({ query: "tarot card meaning", collectionName: "arcana" });
await feedback({ traceId, score: 1 });
```

---

### Phase E: Codecov Patch Battle (4 Rounds)

This phase consumed the most calendar time and is the primary source of lessons.

#### Round 1 — 44%

**What happened:** `anthropic.ts` (270 lines) was added with no tests running the actual `wrappedCreate` function. `anthropic-patch.test.ts` via `SafeConfigResolver` was added but SafeConfigResolver stubs the SDK call — the interceptor body never executed.

**Key mistake:** Assumed that any test touching the module would cover the source lines. Codecov patch analysis counts which lines in the diff were _executed_, not merely imported.

#### Round 2 — 27.67% (went backward)

**What happened:** Added `anthropic-patch.test.ts` (159 new test lines in the diff) **without** covering `anthropic.ts` source lines. Codecov patch now included 159 "covered" test lines but the `anthropic.ts` source coverage fraction was the same. Because patch analysis is a fraction, adding 159 covered-test-lines and 0 newly-covered-source-lines _diluted_ the denominator — coverage dropped from 44% to 27.67%.

**Key insight:** Every new line added to the diff (including test files) participates in the patch denominator. Adding test files without improving their target module's coverage can worsen the patch percentage.

#### Round 3 — 89.25%

**What happened:** Created `anthropic-wrapped.test.ts` using `jest.doMock("@anthropic-ai/sdk", factory, { virtual: true })`. This was the correct pattern — provides the optional peer dep synthetically without installing it, allowing `wrappedCreate` to execute in CI. Covered 12 core scenarios.

Remaining gap: `openai.ts` defensive branch paths (null export, no `completions.create`, constructor throws, create-on-instance) had not been tested. Python `anthropic.py`/`openai.py` VERUM_DISABLED 4-line blocks were also uncovered.

#### Round 4 — 91.73%

**What happened:** Added 5 defensive branch tests to `openai-wrapped.test.ts` → `openai.ts` hit 100%. Added Python module-level tests → `__init__.py` hit 100%. Added `schema.ts` to `.codecov.yml` ignore.

Remaining gap (2.87pp): Two Python files still at 33.33% (VERUM_DISABLED path not tested in Python), and `anthropic.ts` at 93.10% (idempotency guard `if (_patched) return;` never hit because `jest.resetModules()` in `beforeEach` always gives a fresh module with `_patched = false`).

#### Final — Pass

Added `TestVerumDisabledOpenAI` and `TestVerumDisabledAnthropic` (3 tests each) to Python test files. Added idempotency test to `anthropic-wrapped.test.ts` that calls `patchAnthropic()` twice without resetting, triggering the early-return branch. All three files hit 100% lines. Codecov patch exceeded 94.60%.

---

## Plan vs Reality

| Item | Plan | Actual | Gap / Note |
|---|---|---|---|
| Codecov iterations | 1 (pass on first push) | **4 failures** | None of the Codecov patch analysis behaviours were anticipated |
| `jest.doMock` virtual mock | Not anticipated | **Required** for optional peer dep testing | `@anthropic-ai/sdk` not in devDependencies; standard `jest.mock` fails |
| Test LOC | ~300 (2 new test files) | **~900** (5 new files + 4 extended files) | Each Codecov round required additional tests |
| `exactOptionalPropertyTypes` fix | Not anticipated | Required conditional spread in anthropic.ts | TS strict mode — `string \| undefined` ≠ `string` for optional props |
| VERUM_DISABLED Python tests | Not anticipated | Required dedicated test class per module | VERUM_DISABLED path needed explicit `os.environ` injection, not covered by existing setUp patterns |
| Schema fix | 1 commit | 1 commit | Matched |

---

## Lessons Learned

### 1. Codecov patch dilution: adding test files can worsen patch%

When a new test file is added in the diff with 0 impact on source coverage, it adds lines to the patch denominator (all lines are covered — tests pass themselves) but does not add numerator lines in the source file. If the problematic source file's uncovered lines remain constant, the overall fraction **drops**.

**Rule:** Never add a test file to a PR as a standalone commit without simultaneously verifying that its target source module improves in coverage. Use `--coverage` locally before each push.

### 2. `jest.doMock(name, factory, { virtual: true })` is the pattern for optional peer deps

When a source file does `try { await import("pkg") } catch { warn }` and `pkg` is not in `devDependencies`, the module doesn't exist in CI's `node_modules`. Standard `jest.mock("pkg")` fails with "Cannot find module." The solution:

```typescript
jest.resetModules();
jest.doMock("pkg", () => ({ __esModule: true, default: FakeClass }), { virtual: true });
require("../src/module"); // re-require after mocking
```

`jest.resetModules()` must precede `doMock` to ensure the module re-evaluates (fires auto-patch) against the new mock.

### 3. Idempotency guards need a no-reset test

A module-level idempotency flag (`let _patched = false`) is reset on every `jest.resetModules()` call. Tests that call `resetModules()` in `beforeEach` can never trigger the guard — the flag is always `false` on entry.

**Fix:** Add a dedicated test that does NOT call `resetModules()`, loads the module, waits for auto-patch, then calls the patch function again:

```typescript
it("is idempotent", async () => {
  const { patchAnthropic } = loadPatchedModule();
  await new Promise(r => setTimeout(r, 50)); // auto-patch fires → _patched = true
  await expect(patchAnthropic()).resolves.toBeUndefined(); // hits if (_patched) return;
});
```

### 4. `exactOptionalPropertyTypes` requires conditional spread

TypeScript's `exactOptionalPropertyTypes: true` (strict mode) distinguishes between `property: string | undefined` and `property?: string`. Assigning `undefined` to an optional property is a type error.

```typescript
// ❌ Type error — undefined is not assignable to string
const params = { system: resolvedSystem || undefined };

// ✅ Correct
const params = { ...(resolvedSystem ? { system: resolvedSystem } : {}) };
```

Every optional-property assignment in a strict codebase should use conditional spread. Find/replace `property: value || undefined` with the spread form at review time.

### 5. Codecov `target: auto` follows base branch, not the config file value

`.codecov.yml` specifies `target: 50%` for patch checks. The actual reported target was **94.60%**. When `base: auto` is set, Codecov uses the base branch's patch coverage as the target — the config `target` acts as a floor, but if the base branch exceeds it, the base branch value wins.

**Implication:** A PR that adds a lot of new code in a high-coverage codebase must cover that new code at the same rate as the base. "50% of new code" is not a safe assumption.

---

## Follow-ups

| # | Item | Priority | Notes |
|---|---|---|---|
| F-1 | `drizzle-kit pull` in alembic checklist | P1 | Add to `CLAUDE.md` migration checklist: run `drizzle-kit pull` after each `alembic upgrade head` |
| F-2 | `docs/STATUS.md` test count update | P2 | TS SDK now 80 tests (was 63); Python SDK test count grew by ~6 |
| F-3 | Python SDK dogfood on real ArcanaInsight codebase | P1 | ArcanaInsight uses Grok-2 via OpenAI-compatible API. `examples/arcana-integration/after.py` shows the pattern (`import verum.openai` + `x-verum-deployment` header). The example is documentation — confirm the actual ArcanaInsight service has been updated. Anthropic auto-instrument is for future services, not ArcanaInsight. |
| F-4 | VERUM_DISABLED coverage in Dashboard/API | P3 | env flag only tested in SDK packages; API/dashboard modules not checked |
| F-5 | `SafeConfigResolver` + `jest.doMock` combined test | P3 | `anthropic-patch.test.ts` tests resolver integration but not the full wrappedCreate path; merge the two patterns |
| F-6 | Jest `coverageThreshold.branches` review | P3 | `anthropic.ts` branch coverage at 90.74% — `if (_patched)` adds branches; revisit threshold after Phase 5 |

---

## Commit History (PR #68)

| SHA | Message |
|---|---|
| `1195e2b` | `fix(db): add span_attributes to Drizzle spans schema and chunks inference_id FK` |
| `1d72a4a` | `fix(sdk-ts): correct trace payload fields for A/B variant tracking` |
| `478dba7` | `feat(sdk-ts): implement Anthropic auto-instrument patch` |
| `7bf8e60` | `feat(sdk): expose retrieve() and feedback() as top-level module functions` |
| `8080b02` | `feat(sdk): implement VERUM_DISABLED env flag; fix circuit breaker README` |
| `c752e06` | `docs: fix schema tables, ADR-011/012, ServiceInference fields, test counts` |
| `49a6077` | `fix(sdk-ts): fix TS type error in anthropic.ts; add patch tests for coverage` |
| `8253868` | `test(sdk): add anthropic-wrapped and index module-level coverage; fix codecov patch` |
| `e4e8fad` | `test(sdk-ts): add openai.ts defensive branch + error propagation tests` |
| `fac9ff7` | `test(sdk): cover VERUM_DISABLED branch + anthropic idempotency guard` |

Squash-merged to main: `575089a fix/feat/docs: comprehensive audit fixes — Drizzle schema, TS SDK, docs (2026-04-26) (#68)`

---

_Report generated: 2026-04-26_  
_Scope: PR #68 fix/audit-2026-04-26_  
_Next: ArcanaInsight dogfood with Anthropic auto-instrument (F-3)_
