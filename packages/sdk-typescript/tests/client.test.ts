import { DeploymentConfigCache } from "../src/cache.js";
import { chooseVariant } from "../src/router.js";
import { VerumClient } from "../src/client.js";

// ── Cache tests ─────────────────────────────────────────────────────────────

describe("DeploymentConfigCache", () => {
  it("returns undefined for a cache miss", () => {
    const cache = new DeploymentConfigCache();
    expect(cache.get("dep-1")).toBeUndefined();
  });

  it("returns cached value before TTL", () => {
    const cache = new DeploymentConfigCache(60_000);
    cache.set("dep-1", { traffic_split: 0.1 } as never);
    expect(cache.get("dep-1")).toEqual({ traffic_split: 0.1 });
  });

  it("returns undefined after TTL expires", async () => {
    const cache = new DeploymentConfigCache(1); // 1ms TTL
    cache.set("dep-1", { traffic_split: 0.1 } as never);
    await new Promise((r) => setTimeout(r, 5));
    expect(cache.get("dep-1")).toBeUndefined();
  });
});

// ── Router tests ─────────────────────────────────────────────────────────────

describe("chooseVariant", () => {
  it("always returns baseline at 0", () => {
    for (let i = 0; i < 100; i++) expect(chooseVariant(0)).toBe("baseline");
  });

  it("always returns variant at 1", () => {
    for (let i = 0; i < 100; i++) expect(chooseVariant(1)).toBe("variant");
  });

  it("distributes roughly 50/50 at 0.5", () => {
    const results = Array.from({ length: 1000 }, () => chooseVariant(0.5));
    const variantCount = results.filter((r) => r === "variant").length;
    expect(variantCount).toBeGreaterThan(400);
    expect(variantCount).toBeLessThan(600);
  });
});

// ── Timeout tests ─────────────────────────────────────────────────────────────

describe("VerumClient fetch timeout", () => {
  it("aborts request when server hangs past timeoutMs", async () => {
    const client = new VerumClient({
      apiUrl: "http://test.local",
      apiKey: "key",
      timeoutMs: 50,
    });

    const originalFetch = globalThis.fetch;
    globalThis.fetch = jest.fn((_url: unknown, init?: RequestInit) =>
      new Promise<Response>((_, reject) => {
        init?.signal?.addEventListener("abort", () =>
          reject(new DOMException("The operation was aborted", "AbortError"))
        );
      })
    ) as typeof fetch;

    try {
      await expect(
        client.retrieve({ query: "test", collectionName: "col" })
      ).rejects.toThrow();
    } finally {
      globalThis.fetch = originalFetch;
    }
  });
});

// ── Client tests ─────────────────────────────────────────────────────────────

describe("VerumClient.chat", () => {
  it("passes through when no deploymentId", async () => {
    const client = new VerumClient({ apiUrl: "http://test.local", apiKey: "key" });
    const messages = [{ role: "user" as const, content: "Hello" }];
    const result = await client.chat({ messages, model: "gpt-4" });
    expect(result.routed_to).toBe("baseline");
    expect(result.deployment_id).toBeNull();
    // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
    expect(result.messages[0]!.content).toBe("Hello");
  });

  it("replaces system prompt with variant when routed to variant", async () => {
    const client = new VerumClient({ apiUrl: "http://test.local", apiKey: "key" });
    // Inject a mock config into the cache directly
    (client as unknown as { cache: DeploymentConfigCache<unknown> }).cache.set("dep-1", {
      deployment_id: "dep-1",
      status: "canary",
      traffic_split: 1.0,  // 100% to variant — always triggers
      variant_prompt: "CoT variant prompt",
    });

    const messages = [
      { role: "system" as const, content: "Original system prompt" },
      { role: "user" as const, content: "User question" },
    ];
    const result = await client.chat({ messages, deploymentId: "dep-1", model: "grok-2-1212" });
    expect(result.routed_to).toBe("variant");
    // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
    expect(result.messages[0]!.content).toBe("CoT variant prompt");
    // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
    expect(result.messages[1]!.content).toBe("User question");
  });
});
