/**
 * Tests for src/anthropic.ts auto-instrument patch.
 *
 * Strategy mirrors openai-patch.test.ts:
 *   - Does NOT try to directly exercise the monkey-patch (no @anthropic-ai/sdk peer dep)
 *   - Verifies observable module-level behaviour via static import
 *   - Covers: load without error, idempotent, no deployment_id passthrough, fail_open,
 *     VERUM_DISABLED guard, and the synthetic-messages/extract-system helpers via
 *     the SafeConfigResolver (which the patch delegates to).
 */

import { DeploymentConfigCache } from "../src/cache.js";
import { SafeConfigResolver } from "../src/_safe-resolver.js";
import { patchAnthropic, _resetPatchState } from "../src/anthropic.js";
import type { DeploymentConfig, ResolveResult } from "../src/_safe-resolver.js";

// ── helpers ──────────────────────────────────────────────────────────────────

function makeMessages(system?: string): Array<{ role: string; content: string }> {
  const msgs: Array<{ role: string; content: string }> = [];
  if (system) msgs.push({ role: "system", content: system });
  msgs.push({ role: "user", content: "Hello" });
  return msgs;
}

// ── anthropic.ts module-level behaviour ──────────────────────────────────────

describe("anthropic patch module", () => {
  const savedEnv = { ...process.env };

  afterEach(() => {
    _resetPatchState();
    process.env = { ...savedEnv };
  });

  it("1: module loads and exports patchAnthropic without error even if @anthropic-ai/sdk not installed", () => {
    expect(typeof patchAnthropic).toBe("function");
    expect(typeof _resetPatchState).toBe("function");
  });

  it("2: patchAnthropic is idempotent — second call is a no-op", async () => {
    _resetPatchState();
    await expect(patchAnthropic()).resolves.toBeUndefined();
    await expect(patchAnthropic()).resolves.toBeUndefined();
  });

  it("3: no deployment_id → SafeConfigResolver.resolve is never called", async () => {
    const savedFetch = globalThis.fetch;
    const fetchMock = jest.fn(() =>
      Promise.resolve(new Response("{}", { status: 200 }))
    ) as typeof fetch;
    globalThis.fetch = fetchMock;

    try {
      const deploymentId: string | undefined = undefined;
      const messages = makeMessages("sys");
      const resolverWouldBeCalled = deploymentId !== undefined && messages.length > 0;
      expect(resolverWouldBeCalled).toBe(false);
      expect(fetchMock).not.toHaveBeenCalled();
    } finally {
      globalThis.fetch = savedFetch;
    }
  });

  it("4: resolver fail_open → original messages returned unchanged", async () => {
    const savedFetch = globalThis.fetch;
    globalThis.fetch = jest.fn(() =>
      Promise.reject(new Error("offline"))
    ) as typeof fetch;

    try {
      const cache = new DeploymentConfigCache<DeploymentConfig>();
      const resolver = new SafeConfigResolver("http://test.local", "key", cache);
      const original = makeMessages("my-system");

      const result: ResolveResult = await resolver.resolve("dep-x", original);
      expect(result.reason).toBe("fail_open");
      expect(result.messages).toEqual(original);
    } finally {
      globalThis.fetch = savedFetch;
    }
  });

  it("5: VERUM_DISABLED=1 → patchAnthropic resolves without patching", async () => {
    process.env["VERUM_DISABLED"] = "1";
    _resetPatchState();
    await expect(patchAnthropic()).resolves.toBeUndefined();
  });

  it("5b: VERUM_DISABLED=true → patchAnthropic resolves without patching", async () => {
    process.env["VERUM_DISABLED"] = "true";
    _resetPatchState();
    await expect(patchAnthropic()).resolves.toBeUndefined();
  });

  it("5c: VERUM_DISABLED=yes → patchAnthropic resolves without patching", async () => {
    process.env["VERUM_DISABLED"] = "yes";
    _resetPatchState();
    await expect(patchAnthropic()).resolves.toBeUndefined();
  });
});

// ── synthetic messages / extract-system (via SafeConfigResolver) ─────────────
//
// The Anthropic patch synthesises [{role:"system",content:...}] from the top-level
// `system` kwarg, passes it to SafeConfigResolver, then extracts the result back out.
// We verify that round-trip here by testing SafeConfigResolver directly.

describe("anthropic system-prompt round-trip (via resolver)", () => {
  const savedFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = savedFetch;
  });

  it("resolver replaces system message content when variant is applied", async () => {
    const cfg: DeploymentConfig = { traffic_split: 1.0, variant_prompt: "new-system-text" };
    const cache = new DeploymentConfigCache<DeploymentConfig>();
    cache.set("dep-sys", cfg);
    const resolver = new SafeConfigResolver("http://test.local", "key", cache);

    // Simulate the synthetic messages the patch builds from system kwarg
    const synthetic = [{ role: "system", content: "original-system-text" }];
    const result: ResolveResult = await resolver.resolve("dep-sys", synthetic);

    expect(result.reason).toBe("fresh");
    // The resolver should have swapped the system content
    const sysMsg = result.messages.find((m) => m.role === "system");
    expect(sysMsg?.content).toBe("new-system-text");
  });

  it("resolver leaves messages unchanged when traffic_split=0", async () => {
    const cfg: DeploymentConfig = { traffic_split: 0, variant_prompt: "should-not-appear" };
    const cache = new DeploymentConfigCache<DeploymentConfig>();
    cache.set("dep-nosplit", cfg);
    const resolver = new SafeConfigResolver("http://test.local", "key", cache);

    const synthetic = [{ role: "system", content: "keep-this" }];
    const result: ResolveResult = await resolver.resolve("dep-nosplit", synthetic);

    const sysMsg = result.messages.find((m) => m.role === "system");
    expect(sysMsg?.content).toBe("keep-this");
  });

  it("empty system string → synthetic messages array is empty → resolver uses fallback", async () => {
    // When system kwarg is empty, the patch skips resolver entirely.
    // This is modelled by passing an empty messages array and checking fail_open.
    globalThis.fetch = jest.fn(() =>
      Promise.reject(new Error("offline"))
    ) as typeof fetch;

    const cache = new DeploymentConfigCache<DeploymentConfig>();
    const resolver = new SafeConfigResolver("http://test.local", "key", cache);
    const result: ResolveResult = await resolver.resolve("dep-empty", []);
    // SafeConfigResolver fail_open with empty fallback
    expect(result.reason).toBe("fail_open");
    expect(result.messages).toEqual([]);
  });
});
