/**
 * Tests for src/openai.ts wrappedCreate and _sendTrace, exercised via
 * jest.doMock("openai", ..., { virtual: true }) + jest.resetModules()
 * so the optional peer dep is provided synthetically in CI.
 *
 * Pattern rationale:
 *  - openai.ts auto-patches on module import (void _patchOpenAI() at bottom).
 *  - jest.resetModules() + jest.doMock("openai", factory, { virtual: true })
 *    guarantees a fresh module registry on each test, so the auto-patch fires
 *    against our mock OpenAI class every time.
 *  - require() (not import()) loads the freshly-reset module after mocking.
 */

// ── Mock factory ─────────────────────────────────────────────────────────────

interface MockMessage { role: string; content: string }

interface MockChatParams {
  messages?: MockMessage[];
  extra_headers?: Record<string, string>;
  model?: string;
  [key: string]: unknown;
}

interface MockOpenAIModule {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  OpenAI: new (opts?: unknown) => any;
  _mockOrigCreate: jest.Mock;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  _Completions: new () => any;
}

/**
 * Build a fresh mock openai module each time.
 * IMPORTANT: create must be on Completions.prototype, not an instance property,
 * because openai.ts does Object.getPrototypeOf(instance.chat.completions) and
 * checks if prototype["create"] is a function.
 */
function makeMockOpenAIModule(): MockOpenAIModule {
  const mockOrigCreate = jest.fn().mockResolvedValue({
    choices: [{ message: { content: "answer" } }],
    model: "gpt-4",
    usage: { prompt_tokens: 10, completion_tokens: 5 },
  });

  class Completions {
    // create is set on the prototype below
  }
  (Completions.prototype as Record<string, unknown>)["create"] = mockOrigCreate;

  class Chat {
    completions = new Completions();
  }

  class OpenAI {
    chat = new Chat();
    constructor(_options?: unknown) {}
  }

  return { OpenAI, _mockOrigCreate: mockOrigCreate, _Completions: Completions };
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function loadPatchedModule(): {
  patchOpenAI: () => Promise<void>;
  _resetPatchState: () => void;
} {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  return require("../src/openai") as {
    patchOpenAI: () => Promise<void>;
    _resetPatchState: () => void;
  };
}

function getWrappedCreate(mockModule: MockOpenAIModule): jest.Mock {
  const client = new mockModule.OpenAI({ apiKey: "test" });
  return (client.chat.completions as Record<string, jest.Mock>)["create"] as jest.Mock;
}

// ── Test suite ────────────────────────────────────────────────────────────────

describe("openai.ts — wrappedCreate and _sendTrace (virtual openai mock)", () => {
  let mockModule: MockOpenAIModule;
  const savedEnv: Record<string, string | undefined> = {};

  beforeEach(() => {
    jest.resetModules();

    mockModule = makeMockOpenAIModule();

    jest.doMock(
      "openai",
      () => ({ __esModule: true, default: mockModule.OpenAI, OpenAI: mockModule.OpenAI }),
      { virtual: true },
    );

    // Save env vars we may mutate
    savedEnv["VERUM_API_URL"] = process.env["VERUM_API_URL"];
    savedEnv["VERUM_API_KEY"] = process.env["VERUM_API_KEY"];
    savedEnv["VERUM_DEPLOYMENT_ID"] = process.env["VERUM_DEPLOYMENT_ID"];

    // Clean slate for each test
    delete process.env["VERUM_API_URL"];
    delete process.env["VERUM_API_KEY"];
    delete process.env["VERUM_DEPLOYMENT_ID"];
  });

  afterEach(() => {
    jest.dontMock("openai");

    // Restore env
    for (const [k, v] of Object.entries(savedEnv)) {
      if (v === undefined) {
        delete process.env[k];
      } else {
        process.env[k] = v;
      }
    }
  });

  // ── Test 1: patch is applied ─────────────────────────────────────────────

  it("patchOpenAI() replaces create on Completions.prototype", async () => {
    const originalCreate = mockModule._Completions.prototype["create" as keyof typeof mockModule._Completions.prototype];

    // Requiring the module fires void _patchOpenAI() automatically
    loadPatchedModule();

    // Give the fire-and-forget async patch time to run
    await new Promise((r) => setTimeout(r, 50));

    const patchedCreate = mockModule._Completions.prototype["create" as keyof typeof mockModule._Completions.prototype];
    expect(patchedCreate).not.toBe(originalCreate);
    expect(typeof patchedCreate).toBe("function");
  });

  // ── Test 2: passthrough when no deploymentId ─────────────────────────────

  it("wrappedCreate passes through unchanged when no deploymentId and no env var", async () => {
    loadPatchedModule();
    await new Promise((r) => setTimeout(r, 50));

    const wrappedCreate = getWrappedCreate(mockModule);
    const params: MockChatParams = {
      model: "gpt-4",
      messages: [{ role: "user", content: "hi" }],
    };

    await wrappedCreate(params);

    expect(mockModule._mockOrigCreate).toHaveBeenCalledTimes(1);
    const calledParams = mockModule._mockOrigCreate.mock.calls[0]?.[0] as MockChatParams;
    expect(calledParams).toEqual(params);
  });

  // ── Test 3: passthrough when no messages ─────────────────────────────────

  it("wrappedCreate passes through when deploymentId present but no messages", async () => {
    process.env["VERUM_DEPLOYMENT_ID"] = "dep-nomessages";

    loadPatchedModule();
    await new Promise((r) => setTimeout(r, 50));

    const wrappedCreate = getWrappedCreate(mockModule);
    const params: MockChatParams = { model: "gpt-4" }; // no messages key

    await wrappedCreate(params);

    expect(mockModule._mockOrigCreate).toHaveBeenCalledTimes(1);
    const calledParams = mockModule._mockOrigCreate.mock.calls[0]?.[0] as MockChatParams;
    expect(calledParams).toEqual(params);
  });

  // ── Test 4: resolver called and resolved messages forwarded ──────────────

  it("wrappedCreate calls resolver and forwards resolved messages when fetch succeeds", async () => {
    process.env["VERUM_API_URL"] = "http://test.local";
    process.env["VERUM_API_KEY"] = "testkey";

    const variantSys = "You are a variant system prompt";
    const cfgResponse = { traffic_split: 1.0, variant_prompt: variantSys };

    globalThis.fetch = jest.fn().mockResolvedValue(
      new Response(JSON.stringify(cfgResponse), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    ) as typeof fetch;

    loadPatchedModule();
    await new Promise((r) => setTimeout(r, 50));

    const wrappedCreate = getWrappedCreate(mockModule);
    const params: MockChatParams = {
      model: "gpt-4",
      extra_headers: { "x-verum-deployment": "dep-variant" },
      messages: [
        { role: "system", content: "original system" },
        { role: "user", content: "question" },
      ],
    };

    await wrappedCreate(params);

    expect(mockModule._mockOrigCreate).toHaveBeenCalledTimes(1);
    const calledParams = mockModule._mockOrigCreate.mock.calls[0]?.[0] as MockChatParams;
    // Resolver replaces first system message with variantSys
    expect(calledParams.messages?.[0]?.content).toBe(variantSys);
  });

  // ── Test 5: fail-open when resolver throws ───────────────────────────────

  it("wrappedCreate is fail-open when resolver fetch rejects", async () => {
    process.env["VERUM_API_URL"] = "http://test.local";

    globalThis.fetch = jest.fn().mockRejectedValue(
      new Error("network error"),
    ) as typeof fetch;

    loadPatchedModule();
    await new Promise((r) => setTimeout(r, 50));

    const wrappedCreate = getWrappedCreate(mockModule);
    const originalMessages: MockMessage[] = [
      { role: "system", content: "keep me" },
      { role: "user", content: "hello" },
    ];
    const params: MockChatParams = {
      model: "gpt-4",
      extra_headers: { "x-verum-deployment": "dep-failopen" },
      messages: originalMessages,
    };

    const result = await wrappedCreate(params);

    // origCreate still called
    expect(mockModule._mockOrigCreate).toHaveBeenCalledTimes(1);
    // Response comes through normally
    expect(result).toBeDefined();
    // Messages passed to origCreate must be the originals (fail-open)
    const calledParams = mockModule._mockOrigCreate.mock.calls[0]?.[0] as MockChatParams;
    expect(calledParams.messages?.[0]?.content).toBe("keep me");
  });

  // ── Test 6: x-verum-deployment stripped from extra_headers ───────────────

  it("wrappedCreate strips x-verum-deployment but keeps other headers", async () => {
    process.env["VERUM_API_URL"] = "http://test.local";

    // Resolver fails → fail-open path, but still strips the header
    globalThis.fetch = jest.fn().mockRejectedValue(
      new Error("net error"),
    ) as typeof fetch;

    loadPatchedModule();
    await new Promise((r) => setTimeout(r, 50));

    const wrappedCreate = getWrappedCreate(mockModule);
    await wrappedCreate({
      model: "gpt-4",
      extra_headers: {
        "x-verum-deployment": "dep-strip",
        "x-custom": "keep-this",
        "authorization": "Bearer tok",
      },
      messages: [{ role: "user", content: "hi" }],
    });

    const calledParams = mockModule._mockOrigCreate.mock.calls[0]?.[0] as MockChatParams;
    expect(calledParams.extra_headers?.["x-verum-deployment"]).toBeUndefined();
    expect(calledParams.extra_headers?.["x-custom"]).toBe("keep-this");
    expect(calledParams.extra_headers?.["authorization"]).toBe("Bearer tok");
  });

  // ── Test 7: _sendTrace fires fetch when VERUM_API_URL is set ─────────────

  it("_sendTrace fires a POST fetch to /api/v1/traces after create resolves", async () => {
    process.env["VERUM_API_URL"] = "http://traces.local";
    process.env["VERUM_API_KEY"] = "tracekey";

    // Two different fetch calls: one for resolver config, one for trace.
    // Let config fetch fail (fail-open) so we can isolate the trace call.
    const fetchMock = jest.fn()
      .mockRejectedValueOnce(new Error("config fetch fail"))
      .mockResolvedValue(new Response("{}", { status: 200 }));
    globalThis.fetch = fetchMock as typeof fetch;

    loadPatchedModule();
    await new Promise((r) => setTimeout(r, 50));

    const wrappedCreate = getWrappedCreate(mockModule);
    await wrappedCreate({
      model: "gpt-4",
      extra_headers: { "x-verum-deployment": "dep-trace" },
      messages: [{ role: "user", content: "hi" }],
    });

    // Wait for fire-and-forget _sendTrace to complete
    await new Promise((r) => setTimeout(r, 50));

    // At least one fetch call must be to the traces endpoint
    const traceCall = fetchMock.mock.calls.find(
      (call) => typeof call[0] === "string" && (call[0] as string).includes("/api/v1/traces"),
    );
    expect(traceCall).toBeDefined();
    const [url, init] = traceCall as [string, RequestInit];
    expect(url).toBe("http://traces.local/api/v1/traces");
    expect((init as { method: string }).method).toBe("POST");
  });

  // ── Test 8: _sendTrace skips fetch when no VERUM_API_URL ─────────────────

  it("_sendTrace does NOT fire fetch when VERUM_API_URL is absent", async () => {
    // VERUM_API_URL is already unset in beforeEach

    const fetchMock = jest.fn();
    globalThis.fetch = fetchMock as typeof fetch;

    loadPatchedModule();
    await new Promise((r) => setTimeout(r, 50));

    const wrappedCreate = getWrappedCreate(mockModule);

    // With no VERUM_API_URL there is no resolver URL, so resolver returns fail_open
    // without fetching. Then _sendTrace early-returns because !apiUrl.
    process.env["VERUM_DEPLOYMENT_ID"] = "dep-notrace";
    await wrappedCreate({
      model: "gpt-4",
      messages: [{ role: "user", content: "hi" }],
    });

    await new Promise((r) => setTimeout(r, 50));

    // No fetch calls at all (resolver never fetches without a URL, and _sendTrace exits)
    const traceCalls = fetchMock.mock.calls.filter(
      (call) => typeof call[0] === "string" && (call[0] as string).includes("/api/v1/traces"),
    );
    expect(traceCalls).toHaveLength(0);
  });
});
