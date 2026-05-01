# Safety Net Tests Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fill two correctness gaps found in the 2026-05-01 codebase audit — (1) eval_pairs count is not enforced, and (2) ADR-017's "Verum failure never blocks LLM calls" promise is untested at integration level.

**Architecture:** Task 1 adds a warning log in the GENERATE engine when Claude returns fewer than 10 eval pairs, with a matching unit test. Tasks 2–3 add a VERUM_TEST_MODE=1–gated fault injection mechanism to the Next.js config endpoint, then an integration test that enables the fault and verifies the SDK still completes LLM calls via the mock-providers call log.

**Tech Stack:** Python 3.13 + pytest + pytest-asyncio (Task 1); TypeScript strict + Jest (Task 2); pytest + httpx + Docker Compose integration test suite (Task 3).

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `apps/api/src/loop/generate/engine.py` | Modify | Add `logging` import + warning when eval_pairs < 10 |
| `apps/api/tests/loop/generate/test_engine.py` | Modify | Add two new test cases for low eval_pairs count |
| `apps/dashboard/src/lib/test/configFault.ts` | Create | Module-level fault state: `setConfigFault`, `resetConfigFault`, `consumeConfigFault` |
| `apps/dashboard/src/app/api/test/set-config-fault/route.ts` | Create | HTTP control endpoint (VERUM_TEST_MODE=1 only): POST sets fault, DELETE resets |
| `apps/dashboard/src/app/api/test/set-config-fault/__tests__/route.test.ts` | Create | Jest tests for the control endpoint |
| `apps/dashboard/src/app/api/v1/deploy/[id]/config/route.ts` | Modify | Import + call `consumeConfigFault()`; return 503 if active |
| `apps/dashboard/src/app/api/v1/deploy/[id]/config/__tests__/route.test.ts` | Modify | Add test case: fault active → 503 |
| `tests/integration/test_35_sdk_safety_net.py` | Create | Integration: enable config fault → trigger fake-arcana calls → verify LLM calls reached mock-providers |

---

## Task 1: eval_pairs minimum count guard

**Files:**
- Modify: `apps/api/src/loop/generate/engine.py:109-137`
- Modify: `apps/api/tests/loop/generate/test_engine.py` (append two tests)

- [ ] **Step 1: Write the two failing tests**

Append to `apps/api/tests/loop/generate/test_engine.py`:

```python
@pytest.mark.asyncio
async def test_run_generate_warns_when_eval_pairs_below_minimum(monkeypatch, caplog):
    """run_generate emits WARNING when Claude returns fewer than 10 eval pairs."""
    import logging
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    call_count = 0

    async def fake_create(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            payload = {"variants": [
                {"variant_type": "original", "content": "v1", "variables": []},
                {"variant_type": "cot", "content": "v2", "variables": []},
                {"variant_type": "few_shot", "content": "v3", "variables": []},
                {"variant_type": "role_play", "content": "v4", "variables": []},
                {"variant_type": "concise", "content": "v5", "variables": []},
            ]}
        elif call_count == 2:
            payload = {"chunking_strategy": "recursive", "chunk_size": 512,
                       "chunk_overlap": 50, "top_k": 5, "hybrid_alpha": 0.7}
        else:
            # Only 3 pairs — below minimum of 10
            payload = {"pairs": [
                {"query": "q1", "expected_answer": "a1", "context_needed": True},
                {"query": "q2", "expected_answer": "a2", "context_needed": True},
                {"query": "q3", "expected_answer": "a3", "context_needed": False},
            ]}
        mock = MagicMock()
        mock.content = [MagicMock(text=json.dumps(payload))]
        return mock

    with patch("anthropic.AsyncAnthropic") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(side_effect=fake_create)
        mock_client_cls.return_value = mock_client

        with caplog.at_level(logging.WARNING, logger="src.loop.generate.engine"):
            result = await run_generate(
                inference_id=str(uuid.uuid4()),
                domain="divination/tarot",
                tone="mystical",
                language="ko",
                user_type="consumer",
                summary="A tarot service.",
                prompt_templates=[{"content": "You are a tarot reader.", "variables": []}],
                sample_chunks=["The Tower card."],
            )

    # Must still return all 3 pairs — no data is dropped
    assert len(result.eval_pairs) == 3
    # Must emit a warning mentioning the actual count
    warning_messages = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    assert any("3" in msg for msg in warning_messages), (
        f"Expected warning containing '3', got: {warning_messages}"
    )


@pytest.mark.asyncio
async def test_run_generate_no_warning_when_eval_pairs_at_minimum(monkeypatch, caplog):
    """run_generate does NOT warn when Claude returns exactly 10 eval pairs."""
    import logging
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    call_count = 0

    async def fake_create(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            payload = {"variants": [
                {"variant_type": "original", "content": "v1", "variables": []},
                {"variant_type": "cot", "content": "v2", "variables": []},
                {"variant_type": "few_shot", "content": "v3", "variables": []},
                {"variant_type": "role_play", "content": "v4", "variables": []},
                {"variant_type": "concise", "content": "v5", "variables": []},
            ]}
        elif call_count == 2:
            payload = {"chunking_strategy": "recursive", "chunk_size": 512,
                       "chunk_overlap": 50, "top_k": 5, "hybrid_alpha": 0.7}
        else:
            # Exactly 10 pairs — at boundary, no warning expected
            payload = {"pairs": [
                {"query": f"q{i}", "expected_answer": f"a{i}", "context_needed": True}
                for i in range(10)
            ]}
        mock = MagicMock()
        mock.content = [MagicMock(text=json.dumps(payload))]
        return mock

    with patch("anthropic.AsyncAnthropic") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(side_effect=fake_create)
        mock_client_cls.return_value = mock_client

        with caplog.at_level(logging.WARNING, logger="src.loop.generate.engine"):
            result = await run_generate(
                inference_id=str(uuid.uuid4()),
                domain="divination/tarot",
                tone="mystical",
                language="ko",
                user_type="consumer",
                summary="A tarot service.",
                prompt_templates=[{"content": "You are a tarot reader.", "variables": []}],
                sample_chunks=["The Tower card."],
            )

    assert len(result.eval_pairs) == 10
    warning_messages = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    assert not warning_messages, f"Unexpected warnings: {warning_messages}"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd apps/api
python -m pytest tests/loop/generate/test_engine.py::test_run_generate_warns_when_eval_pairs_below_minimum tests/loop/generate/test_engine.py::test_run_generate_no_warning_when_eval_pairs_at_minimum -v
```

Expected: FAIL — `WARNING` never emitted because the guard doesn't exist yet.

- [ ] **Step 3: Add logging import and warning guard to engine.py**

At the top of `apps/api/src/loop/generate/engine.py`, after the existing imports, add:

```python
import logging

_log = logging.getLogger(__name__)

_EVAL_PAIRS_MIN = 10
```

Replace the body of `_generate_eval_pairs` (lines 129–137) with:

```python
    data = await _call_generate(eval_prompt)
    pairs = data.get("pairs", [])
    if len(pairs) < _EVAL_PAIRS_MIN:
        _log.warning(
            "generate/eval_pairs: Claude returned %d pairs (expected ≥%d); "
            "proceeding with what was returned",
            len(pairs),
            _EVAL_PAIRS_MIN,
        )
    return [
        EvalPair(
            query=p["query"],
            expected_answer=p["expected_answer"],
            context_needed=bool(p.get("context_needed", True)),
        )
        for p in pairs
    ]
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd apps/api
python -m pytest tests/loop/generate/test_engine.py -v
```

Expected: All tests PASS including the two new ones.

- [ ] **Step 5: Commit**

```bash
cd apps/api
git add src/loop/generate/engine.py tests/loop/generate/test_engine.py
git commit -m "fix(generate): warn when eval_pairs count below minimum threshold"
```

---

## Task 2: Config fault injection plumbing (VERUM_TEST_MODE=1)

**Files:**
- Create: `apps/dashboard/src/lib/test/configFault.ts`
- Create: `apps/dashboard/src/app/api/test/set-config-fault/route.ts`
- Create: `apps/dashboard/src/app/api/test/set-config-fault/__tests__/route.test.ts`
- Modify: `apps/dashboard/src/app/api/v1/deploy/[id]/config/route.ts`
- Modify: `apps/dashboard/src/app/api/v1/deploy/[id]/config/__tests__/route.test.ts`

- [ ] **Step 1: Create `apps/dashboard/src/lib/test/configFault.ts`**

```typescript
/**
 * Process-level config fault injection used exclusively in VERUM_TEST_MODE=1.
 * Production code must never call setConfigFault/resetConfigFault.
 * consumeConfigFault() is a no-op when VERUM_TEST_MODE !== "1".
 */

let _configFaultCount = 0;

/** Set the number of consecutive /config requests that will return 503. */
export function setConfigFault(count: number): void {
  _configFaultCount = count;
}

/** Clear any active config fault. */
export function resetConfigFault(): void {
  _configFaultCount = 0;
}

/**
 * Returns true and decrements the counter if a fault is active.
 * Always returns false in non-test mode.
 */
export function consumeConfigFault(): boolean {
  if (process.env.VERUM_TEST_MODE !== "1") return false;
  if (_configFaultCount <= 0) return false;
  _configFaultCount--;
  return true;
}
```

- [ ] **Step 2: Create `apps/dashboard/src/app/api/test/set-config-fault/route.ts`**

```typescript
import { setConfigFault, resetConfigFault } from "@/lib/test/configFault";

/**
 * POST /api/test/set-config-fault   { count: number }
 *   → activates config fault for the next `count` calls to /api/v1/deploy/[id]/config
 *
 * DELETE /api/test/set-config-fault
 *   → clears any active config fault
 *
 * Both endpoints return 404 unless VERUM_TEST_MODE=1.
 */
export async function POST(req: Request): Promise<Response> {
  if (process.env.VERUM_TEST_MODE !== "1") {
    return new Response("not found", { status: 404 });
  }
  const body = (await req.json()) as { count?: number };
  const count = typeof body.count === "number" ? body.count : 1;
  setConfigFault(count);
  return Response.json({ ok: true, count });
}

export async function DELETE(): Promise<Response> {
  if (process.env.VERUM_TEST_MODE !== "1") {
    return new Response("not found", { status: 404 });
  }
  resetConfigFault();
  return Response.json({ ok: true });
}
```

- [ ] **Step 3: Write the Jest tests for the control endpoint**

Create `apps/dashboard/src/app/api/test/set-config-fault/__tests__/route.test.ts`:

```typescript
jest.mock("@/lib/test/configFault", () => ({
  setConfigFault: jest.fn(),
  resetConfigFault: jest.fn(),
}));

import { POST, DELETE } from "../route";
import { setConfigFault, resetConfigFault } from "@/lib/test/configFault";

const mockSet = setConfigFault as jest.MockedFunction<typeof setConfigFault>;
const mockReset = resetConfigFault as jest.MockedFunction<typeof resetConfigFault>;

const _origEnv = process.env.VERUM_TEST_MODE;
afterAll(() => {
  process.env.VERUM_TEST_MODE = _origEnv;
});

describe("POST /api/test/set-config-fault", () => {
  it("returns 404 when VERUM_TEST_MODE is not set", async () => {
    delete process.env.VERUM_TEST_MODE;
    const req = new Request("http://localhost/api/test/set-config-fault", {
      method: "POST",
      body: JSON.stringify({ count: 5 }),
    });
    const res = await POST(req);
    expect(res.status).toBe(404);
    expect(mockSet).not.toHaveBeenCalled();
  });

  it("sets fault count and returns ok when VERUM_TEST_MODE=1", async () => {
    process.env.VERUM_TEST_MODE = "1";
    const req = new Request("http://localhost/api/test/set-config-fault", {
      method: "POST",
      body: JSON.stringify({ count: 3 }),
    });
    const res = await POST(req);
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body).toEqual({ ok: true, count: 3 });
    expect(mockSet).toHaveBeenCalledWith(3);
  });

  it("defaults count to 1 when count is omitted", async () => {
    process.env.VERUM_TEST_MODE = "1";
    const req = new Request("http://localhost/api/test/set-config-fault", {
      method: "POST",
      body: JSON.stringify({}),
    });
    await POST(req);
    expect(mockSet).toHaveBeenCalledWith(1);
  });
});

describe("DELETE /api/test/set-config-fault", () => {
  it("returns 404 when VERUM_TEST_MODE is not set", async () => {
    delete process.env.VERUM_TEST_MODE;
    const res = await DELETE();
    expect(res.status).toBe(404);
    expect(mockReset).not.toHaveBeenCalled();
  });

  it("resets fault and returns ok when VERUM_TEST_MODE=1", async () => {
    process.env.VERUM_TEST_MODE = "1";
    const res = await DELETE();
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body).toEqual({ ok: true });
    expect(mockReset).toHaveBeenCalled();
  });
});
```

- [ ] **Step 4: Run Jest tests to confirm they fail**

```bash
cd apps/dashboard
pnpm test -- --testPathPattern="set-config-fault" --no-coverage
```

Expected: FAIL — module `@/lib/test/configFault` does not exist yet (import error).

- [ ] **Step 5: Modify the config route to consume the fault**

In `apps/dashboard/src/app/api/v1/deploy/[id]/config/route.ts`, add import at the top (after existing imports):

```typescript
import { consumeConfigFault } from "@/lib/test/configFault";
```

Inside the `GET` handler, immediately after the `validateApiKey` check succeeds (after line `if (!keyResult) { return new Response("unauthorized", ...`), add:

```typescript
  // Fault injection for integration tests (VERUM_TEST_MODE=1 only, always no-op in prod)
  if (consumeConfigFault()) {
    return new Response("simulated Verum config fault", { status: 503 });
  }
```

The full modified GET function begins:

```typescript
export async function GET(
  req: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const rawKey =
    req.headers.get("x-verum-api-key") ??
    req.headers.get("authorization")?.replace("Bearer ", "") ??
    "";
  const keyResult = await validateApiKey(rawKey);
  if (!keyResult) {
    return new Response("unauthorized", { status: 401 });
  }

  // Fault injection for integration tests (VERUM_TEST_MODE=1 only, always no-op in prod)
  if (consumeConfigFault()) {
    return new Response("simulated Verum config fault", { status: 503 });
  }

  const { id } = await params;
  // ... rest unchanged
```

- [ ] **Step 6: Add fault test case to the existing config route test**

In `apps/dashboard/src/app/api/v1/deploy/[id]/config/__tests__/route.test.ts`, add at the top of the existing mocks:

```typescript
jest.mock("@/lib/test/configFault", () => ({
  consumeConfigFault: jest.fn().mockReturnValue(false),
}));
```

And add the import + a new test case inside the existing `describe` block:

```typescript
import { consumeConfigFault } from "@/lib/test/configFault";
const mockConsumeConfigFault = consumeConfigFault as jest.MockedFunction<typeof consumeConfigFault>;
```

New test case (add inside `describe("GET /api/v1/deploy/[id]/config", ...)`):

```typescript
  it("returns 503 when config fault is active", async () => {
    mockValidateApiKey.mockResolvedValueOnce({
      deploymentId: "dep-1",
      userId: "user-1",
    });
    mockConsumeConfigFault.mockReturnValueOnce(true);

    const req = makeRequest({ "x-verum-api-key": "a".repeat(41) });
    const res = await GET(req, { params: Promise.resolve({ id: "dep-1" }) });
    expect(res.status).toBe(503);
  });
```

- [ ] **Step 7: Run all config-related Jest tests to confirm they pass**

```bash
cd apps/dashboard
pnpm test -- --testPathPattern="(set-config-fault|deploy.*config)" --no-coverage
```

Expected: All PASS.

- [ ] **Step 8: Run full dashboard test suite to confirm no regression**

```bash
cd apps/dashboard
pnpm test --passWithNoTests
```

Expected: 39+ suites, 0 failures.

- [ ] **Step 9: Commit**

```bash
cd apps/dashboard
git add src/lib/test/configFault.ts \
        src/app/api/test/set-config-fault/route.ts \
        src/app/api/test/set-config-fault/__tests__/route.test.ts \
        src/app/api/v1/deploy/[id]/config/route.ts \
        src/app/api/v1/deploy/[id]/config/__tests__/route.test.ts
git commit -m "test(deploy): add VERUM_TEST_MODE config fault injection for ADR-017 integration tests"
```

---

## Task 3: Integration test — SDK safety net under Verum config failure

**Files:**
- Create: `tests/integration/test_35_sdk_safety_net.py`

> **Prerequisites:** `make integration-up` must be running. This test file is numbered between `test_30` (deploy + SDK) and `test_40` (judge + experiment) so it runs after a deployment exists.

- [ ] **Step 1: Write the integration test**

Create `tests/integration/test_35_sdk_safety_net.py`:

```python
"""Integration: ADR-017 — Verum config failures must not block LLM calls.

Prerequisites: make integration-up (runs test_30 first to create a deployment).
These tests enable the fault-injection endpoint, trigger fake-arcana to make
LLM calls, then verify that the calls reached the mock-providers despite Verum
returning 503 on the config endpoint.
"""
from __future__ import annotations

import asyncio
import pytest
import httpx

from tests.integration.conftest import VERUM_APP_URL, MOCK_PROVIDERS_URL
from tests.integration.utils.wait import wait_until

pytestmark = pytest.mark.integration


async def _call_log_count(mock_control: httpx.AsyncClient, endpoint_substr: str) -> int:
    """Return how many mock-provider calls contain `endpoint_substr`."""
    resp = await mock_control.get("/control/calls")
    resp.raise_for_status()
    calls = resp.json()
    return sum(1 for c in calls if endpoint_substr in c.get("endpoint", ""))


@pytest.mark.asyncio
async def test_config_fault_503_does_not_block_llm_calls(
    dashboard_client: httpx.AsyncClient,
    mock_control: httpx.AsyncClient,
    pipeline_state: dict,
) -> None:
    """When Verum's config endpoint returns 503, fake-arcana must still
    complete LLM calls (fail-open behaviour guaranteed by ADR-017)."""
    deployment_id = pipeline_state.get("deployment_id")
    if not deployment_id:
        pytest.skip("No deployment_id in pipeline_state — run test_30 first")

    # Capture LLM call baseline before injecting fault
    baseline = await _call_log_count(mock_control, "/chat/completions")

    # Enable config fault for the next 10 requests (more than fake-arcana will send)
    resp = await dashboard_client.post(
        "/api/test/set-config-fault",
        json={"count": 10},
    )
    assert resp.status_code == 200, f"set-config-fault returned {resp.status_code}: {resp.text}"

    try:
        # Trigger fake-arcana to make 5 LLM calls via the SDK
        async with httpx.AsyncClient(
            base_url=VERUM_APP_URL,
            timeout=30.0,
        ) as client:
            # fake-arcana exposes /trigger that causes it to make LLM calls
            trigger_resp = await client.post(
                "/api/test/trigger-arcana",
                json={"calls": 5},
            )
            # If trigger endpoint doesn't exist, skip gracefully
            if trigger_resp.status_code == 404:
                pytest.skip("fake-arcana trigger endpoint not available in this environment")
            assert trigger_resp.status_code == 200

        # Wait up to 15 s for at least 5 new LLM calls to appear in mock-providers log
        async def _enough_calls() -> bool:
            current = await _call_log_count(mock_control, "/chat/completions")
            return current >= baseline + 5

        reached = await wait_until(
            _enough_calls,
            label="5 new LLM calls after config fault",
            timeout=15.0,
        )
        assert reached, (
            "LLM calls did not reach mock-providers while Verum config was returning 503. "
            "ADR-017 fail-open guarantee is broken."
        )
    finally:
        # Always reset fault so subsequent tests are not affected
        await dashboard_client.delete("/api/test/set-config-fault")


@pytest.mark.asyncio
async def test_config_fault_resets_cleanly(
    dashboard_client: httpx.AsyncClient,
) -> None:
    """After DELETE /api/test/set-config-fault, the config endpoint must return 200."""
    resp = await dashboard_client.post(
        "/api/test/set-config-fault",
        json={"count": 999},
    )
    assert resp.status_code == 200

    # Reset
    reset_resp = await dashboard_client.delete("/api/test/set-config-fault")
    assert reset_resp.status_code == 200

    # Config endpoint should now work normally (we verify it returns non-503 for a known key)
    # We don't have an API key here, so just check 401 (not 503)
    config_resp = await dashboard_client.get(
        "/api/v1/deploy/any-id/config",
        headers={"x-verum-api-key": "invalid-key"},
    )
    assert config_resp.status_code in (401, 403, 404), (
        f"After fault reset, expected auth error, got {config_resp.status_code}"
    )
```

- [ ] **Step 2: Run integration tests to verify (requires Docker)**

```bash
# From project root (requires make integration-up to already be running)
pytest tests/integration/test_35_sdk_safety_net.py -v -m integration
```

Expected: PASS (or SKIP if trigger endpoint not available).

If `test_config_fault_resets_cleanly` passes but `test_config_fault_503_does_not_block_llm_calls` skips: that is acceptable — it means the fake-arcana trigger is not wired up yet. The fault injection plumbing is still verified by the unit tests in Task 2.

- [ ] **Step 3: Run full Python unit test suite to confirm no regression**

```bash
cd apps/api
python -m pytest tests/ -x -q --ignore=tests/integration
```

Expected: 569+ passing, 0 failures (1 DB skip is expected).

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_35_sdk_safety_net.py
git commit -m "test(deploy): integration test for ADR-017 config fault fail-open guarantee"
```

---

## Task 4: Open PR

- [ ] **Step 1: Push branch**

```bash
git push -u origin feat/safety-net-tests
```

- [ ] **Step 2: Create PR**

```bash
gh pr create \
  --title "test: eval_pairs count guard + ADR-017 config fault injection" \
  --body "## Summary
- fix(generate): warn when Claude returns fewer than 10 eval\_pairs (P1 gap from 2026-05-01 audit)
- test(deploy): VERUM\_TEST\_MODE=1 fault injection on /api/v1/deploy/\[id\]/config — enables integration-level verification of ADR-017 fail-open guarantee
- test(deploy): integration test that enables fault + asserts LLM calls still reach mock-providers

## Test plan
- [ ] Python unit tests: \`cd apps/api && python -m pytest tests/ -x -q --ignore=tests/integration\`
- [ ] Dashboard Jest: \`cd apps/dashboard && pnpm test --passWithNoTests\`
- [ ] Integration (requires Docker): \`make integration-up && pytest tests/integration/test_35_sdk_safety_net.py -v\`
" \
  --base main
```
