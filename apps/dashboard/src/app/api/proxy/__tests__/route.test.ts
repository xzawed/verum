import { POST, GET } from "../[...path]/route";

const mockFetch = jest.fn();
global.fetch = mockFetch as typeof fetch;

jest.mock("@/lib/api/validateApiKey", () => ({
  validateApiKey: jest
    .fn()
    .mockResolvedValue({ deploymentId: "dep-1", userId: "user-1" }),
}));

jest.mock("@/lib/rateLimit", () => ({
  checkRateLimitDual: jest.fn().mockResolvedValue(null),
  getClientIp: jest.fn().mockReturnValue("127.0.0.1"),
}));

jest.mock("@/lib/db/client", () => ({
  db: {
    insert: jest.fn().mockReturnValue({
      values: jest.fn().mockReturnValue({
        returning: jest.fn().mockResolvedValue([{ id: "trace-1" }]),
      }),
    }),
  },
}));

function makeProxyRequest(
  pathSegments: string[],
  body = '{"model":"gpt-4","messages":[]}',
) {
  return new Request(
    `http://localhost/api/proxy/${pathSegments.join("/")}`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-verum-api-key": "vk_test_key_that_is_long_enough_for_validation",
        Authorization: "Bearer sk-real-api-key",
      },
      body,
    },
  );
}

describe("POST /api/proxy/[...path]", () => {
  beforeEach(() => {
    mockFetch.mockResolvedValue(
      new Response(
        JSON.stringify({
          choices: [{ message: { content: "hello" } }],
          usage: { prompt_tokens: 10, completion_tokens: 20 },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
  });

  afterEach(() => mockFetch.mockReset());

  it("returns 401 without valid api key", async () => {
    const { validateApiKey } = await import("@/lib/api/validateApiKey");
    (validateApiKey as jest.Mock).mockResolvedValueOnce(null);
    const req = makeProxyRequest(["openai", "v1", "chat", "completions"]);
    const res = await POST(req, {
      params: Promise.resolve({ path: ["openai", "v1", "chat", "completions"] }),
    });
    expect(res.status).toBe(401);
  });

  it("returns 400 for unknown provider", async () => {
    const req = makeProxyRequest(["unknown-provider", "v1", "chat"]);
    const res = await POST(req, {
      params: Promise.resolve({ path: ["unknown-provider", "v1", "chat"] }),
    });
    expect(res.status).toBe(400);
  });

  it("forwards to OpenAI and returns response", async () => {
    const req = makeProxyRequest(["openai", "v1", "chat", "completions"]);
    const res = await POST(req, {
      params: Promise.resolve({
        path: ["openai", "v1", "chat", "completions"],
      }),
    });
    expect(res.status).toBe(200);
    expect(mockFetch).toHaveBeenCalledWith(
      "https://api.openai.com/v1/chat/completions",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("forwards to Grok (api.x.ai)", async () => {
    const req = makeProxyRequest(["grok", "v1", "chat", "completions"]);
    await POST(req, {
      params: Promise.resolve({ path: ["grok", "v1", "chat", "completions"] }),
    });
    expect(mockFetch).toHaveBeenCalledWith(
      "https://api.x.ai/v1/chat/completions",
      expect.anything(),
    );
  });

  it("returns 502 when upstream is unreachable", async () => {
    mockFetch.mockRejectedValueOnce(new Error("network error"));
    const req = makeProxyRequest(["openai", "v1", "chat", "completions"]);
    const res = await POST(req, {
      params: Promise.resolve({
        path: ["openai", "v1", "chat", "completions"],
      }),
    });
    expect(res.status).toBe(502);
  });
});

describe("GET /api/proxy/[...path]", () => {
  beforeEach(() => {
    mockFetch.mockResolvedValue(
      new Response(JSON.stringify({ object: "list", data: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
  });

  afterEach(() => mockFetch.mockReset());

  it("forwards GET request to provider", async () => {
    const req = new Request("http://localhost/api/proxy/openai/v1/models", {
      method: "GET",
      headers: {
        "x-verum-api-key": "vk_test_key_that_is_long_enough_for_validation",
        Authorization: "Bearer sk-real-api-key",
      },
    });
    const res = await GET(req, {
      params: Promise.resolve({ path: ["openai", "v1", "models"] }),
    });
    expect(res.status).toBe(200);
    expect(mockFetch).toHaveBeenCalledWith(
      "https://api.openai.com/v1/models",
      expect.objectContaining({ method: "GET" }),
    );
  });
});
