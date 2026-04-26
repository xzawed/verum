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

  it("routes to baseline and keeps messages unchanged when variant_prompt is null", async () => {
    const client = new VerumClient({ apiUrl: "http://test.local", apiKey: "key" });
    // traffic_split = 1.0 routes to variant, but variant_prompt is null → no replacement
    (client as unknown as { cache: DeploymentConfigCache<unknown> }).cache.set("dep-2", {
      deployment_id: "dep-2",
      status: "canary",
      traffic_split: 1.0,
      variant_prompt: null,
    });

    const messages = [
      { role: "system" as const, content: "Original system" },
      { role: "user" as const, content: "Question" },
    ];
    const result = await client.chat({ messages, deploymentId: "dep-2", model: "gpt-4" });
    expect(result.routed_to).toBe("variant");
    // messages unchanged because variant_prompt is null
    // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
    expect(result.messages[0]!.content).toBe("Original system");
  });

  it("prepends system message when no existing system message and variant_prompt set", async () => {
    const client = new VerumClient({ apiUrl: "http://test.local", apiKey: "key" });
    (client as unknown as { cache: DeploymentConfigCache<unknown> }).cache.set("dep-3", {
      deployment_id: "dep-3",
      status: "canary",
      traffic_split: 1.0,
      variant_prompt: "New system prompt",
    });

    const messages = [{ role: "user" as const, content: "Hello" }];
    const result = await client.chat({ messages, deploymentId: "dep-3", model: "gpt-4" });
    expect(result.routed_to).toBe("variant");
    expect(result.messages).toHaveLength(2);
    // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
    expect(result.messages[0]!.role).toBe("system");
    // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
    expect(result.messages[0]!.content).toBe("New system prompt");
    // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
    expect(result.messages[1]!.content).toBe("Hello");
  });
});

// ── retrieve() tests ─────────────────────────────────────────────────────────

describe("VerumClient.retrieve", () => {
  let originalFetch: typeof globalThis.fetch;
  beforeEach(() => { originalFetch = globalThis.fetch; });
  afterEach(() => { globalThis.fetch = originalFetch; });

  it("returns chunks on success", async () => {
    const client = new VerumClient({ apiUrl: "http://test.local", apiKey: "key" });
    const chunks = [{ content: "chunk 1" }, { content: "chunk 2" }];
    globalThis.fetch = jest.fn().mockResolvedValue(
      new Response(JSON.stringify({ chunks }), { status: 200 })
    ) as typeof fetch;
    const result = await client.retrieve({ query: "test", collectionName: "my-col" });
    expect(result).toEqual(chunks);
  });

  it("throws when response is not ok", async () => {
    const client = new VerumClient({ apiUrl: "http://test.local", apiKey: "key" });
    globalThis.fetch = jest.fn().mockResolvedValue(
      new Response("error", { status: 500 })
    ) as typeof fetch;
    await expect(client.retrieve({ query: "test", collectionName: "col" })).rejects.toThrow("retrieve failed: 500");
  });
});

// ── feedback() tests ─────────────────────────────────────────────────────────

describe("VerumClient.feedback", () => {
  let originalFetch: typeof globalThis.fetch;
  beforeEach(() => { originalFetch = globalThis.fetch; });
  afterEach(() => { globalThis.fetch = originalFetch; });

  it("resolves without error on success", async () => {
    const client = new VerumClient({ apiUrl: "http://test.local", apiKey: "key" });
    globalThis.fetch = jest.fn().mockResolvedValue(new Response("", { status: 200 })) as typeof fetch;
    await expect(client.feedback({ traceId: "t-1", score: 1 })).resolves.toBeUndefined();
  });

  it("throws when response is not ok", async () => {
    const client = new VerumClient({ apiUrl: "http://test.local", apiKey: "key" });
    globalThis.fetch = jest.fn().mockResolvedValue(new Response("", { status: 400 })) as typeof fetch;
    await expect(client.feedback({ traceId: "t-1", score: -1 })).rejects.toThrow("feedback failed: 400");
  });
});

// ── record() tests ───────────────────────────────────────────────────────────

describe("VerumClient.record", () => {
  let originalFetch: typeof globalThis.fetch;
  beforeEach(() => { originalFetch = globalThis.fetch; });
  afterEach(() => { globalThis.fetch = originalFetch; });

  it("returns trace_id on success", async () => {
    const client = new VerumClient({ apiUrl: "http://test.local", apiKey: "key" });
    globalThis.fetch = jest.fn().mockResolvedValue(
      new Response(JSON.stringify({ trace_id: "trace-abc" }), { status: 201 })
    ) as typeof fetch;
    const result = await client.record({
      deploymentId: "dep-1", variant: "baseline", model: "gpt-4",
      inputTokens: 100, outputTokens: 50, latencyMs: 300,
    });
    expect(result).toBe("trace-abc");
  });

  it("throws when response is not ok", async () => {
    const client = new VerumClient({ apiUrl: "http://test.local", apiKey: "key" });
    globalThis.fetch = jest.fn().mockResolvedValue(new Response("", { status: 500 })) as typeof fetch;
    await expect(client.record({
      deploymentId: "dep-1", variant: "baseline", model: "gpt-4",
      inputTokens: 100, outputTokens: 50, latencyMs: 300,
    })).rejects.toThrow("record failed: 500");
  });
});

// ── getDeploymentConfig (private, tested via chat) ────────────────────────────

describe("VerumClient.chat — getDeploymentConfig cache miss", () => {
  let originalFetch: typeof globalThis.fetch;
  beforeEach(() => { originalFetch = globalThis.fetch; });
  afterEach(() => { globalThis.fetch = originalFetch; });

  it("fetches config from API on cache miss and uses it", async () => {
    const client = new VerumClient({ apiUrl: "http://test.local", apiKey: "key" });
    const config = { deployment_id: "dep-1", status: "canary", traffic_split: 0, variant_prompt: null };
    globalThis.fetch = jest.fn().mockResolvedValue(
      new Response(JSON.stringify(config), { status: 200 })
    ) as typeof fetch;
    const messages = [{ role: "user" as const, content: "Hi" }];
    const result = await client.chat({ messages, deploymentId: "dep-1", model: "gpt-4" });
    expect(result.routed_to).toBe("baseline"); // traffic_split = 0 → always baseline
    expect(globalThis.fetch).toHaveBeenCalledTimes(1);
  });

  it("throws when config fetch fails", async () => {
    const client = new VerumClient({ apiUrl: "http://test.local", apiKey: "key" });
    globalThis.fetch = jest.fn().mockResolvedValue(new Response("", { status: 403 })) as typeof fetch;
    const messages = [{ role: "user" as const, content: "Hi" }];
    await expect(client.chat({ messages, deploymentId: "dep-1", model: "gpt-4" })).rejects.toThrow("config fetch failed: 403");
  });
});

// ── Top-level module retrieve() / feedback() ─────────────────────────────────
// Tests the singleton _getClient() path in src/index.ts.

describe("module-level retrieve() and feedback()", () => {
  let originalFetch: typeof globalThis.fetch;

  beforeEach(() => {
    originalFetch = globalThis.fetch;
    // Provide a base URL so VerumClient has something to call
    process.env["VERUM_API_URL"] = "http://test.local";
    process.env["VERUM_API_KEY"] = "key";
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    delete process.env["VERUM_API_URL"];
    delete process.env["VERUM_API_KEY"];
  });

  it("retrieve() delegates to singleton VerumClient.retrieve()", async () => {
    const { retrieve: moduleRetrieve } = await import("../src/index.js");

    globalThis.fetch = jest.fn().mockResolvedValue(
      new Response(JSON.stringify({ chunks: [{ content: "chunk text" }] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    ) as typeof fetch;

    const result = await moduleRetrieve({ query: "test", collectionName: "col" });
    expect(Array.isArray(result)).toBe(true);
  });

  it("feedback() delegates to singleton VerumClient.feedback()", async () => {
    const { feedback: moduleFeedback } = await import("../src/index.js");

    globalThis.fetch = jest.fn().mockResolvedValue(
      new Response("{}", { status: 200 }),
    ) as typeof fetch;

    await expect(
      moduleFeedback({ traceId: "trace-1", score: 1 }),
    ).resolves.toBeUndefined();
  });
});
