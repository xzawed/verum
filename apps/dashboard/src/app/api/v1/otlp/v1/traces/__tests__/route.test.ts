/**
 * Unit tests for OTLP route helpers and the POST handler.
 *
 * Attribute extraction functions (buildAttrMap, getStringAttr, getIntAttr,
 * calcLatencyMs) are pure — tested without mocks.
 *
 * POST handler tests use jest mocks for DB / auth dependencies.
 */
jest.mock("@/lib/rateLimit", () => ({
  checkRateLimitDual: jest.fn().mockResolvedValue(null),
  getClientIp: jest.fn().mockReturnValue("127.0.0.1"),
}));

jest.mock("@/lib/api/validateApiKey", () => ({
  validateApiKey: jest.fn(),
}));
jest.mock("@/lib/db/queries", () => ({
  getDeployment: jest.fn(),
}));
jest.mock("@/lib/db/jobs", () => ({
  getModelPricing: jest.fn(),
  insertTrace: jest.fn(),
}));
jest.mock("@/lib/db/quota", () => ({
  checkAndIncrementTraceQuota: jest.fn(),
  FREE_LIMITS: { traces: 1000 },
}));

import {
  buildAttrMap,
  getStringAttr,
  getIntAttr,
  calcLatencyMs,
  POST,
} from "../route";
import { validateApiKey } from "@/lib/api/validateApiKey";
import { getDeployment } from "@/lib/db/queries";
import { getModelPricing, insertTrace } from "@/lib/db/jobs";
import { checkAndIncrementTraceQuota } from "@/lib/db/quota";

const mockValidateApiKey = validateApiKey as jest.MockedFunction<typeof validateApiKey>;
const mockGetDeployment = getDeployment as jest.MockedFunction<typeof getDeployment>;
const mockGetModelPricing = getModelPricing as jest.MockedFunction<typeof getModelPricing>;
const mockInsertTrace = insertTrace as jest.MockedFunction<typeof insertTrace>;
const mockCheckQuota = checkAndIncrementTraceQuota as jest.MockedFunction<typeof checkAndIncrementTraceQuota>;

// ── Pure helper unit tests ───────────────────────────────────────────────────

describe("buildAttrMap", () => {
  it("returns empty object for undefined attributes", () => {
    expect(buildAttrMap(undefined)).toEqual({});
  });

  it("extracts stringValue, intValue, doubleValue, and boolValue", () => {
    const attrs = [
      { key: "llm.model_name", value: { stringValue: "gpt-4o" } },
      { key: "llm.token_count.prompt", value: { intValue: 150 } },
      { key: "cost_usd", value: { doubleValue: 0.001234 } },
      { key: "cached", value: { boolValue: true } },
    ];
    const map = buildAttrMap(attrs);
    expect(map["llm.model_name"]).toBe("gpt-4o");
    expect(map["llm.token_count.prompt"]).toBe(150);
    expect(map["cost_usd"]).toBeCloseTo(0.001234);
    expect(map["cached"]).toBe(true);
  });

  it("stores null for a key with no recognized value type", () => {
    const map = buildAttrMap([{ key: "unknown_key", value: {} }]);
    expect(map["unknown_key"]).toBeNull();
  });
});

describe("getStringAttr", () => {
  it("returns the string when present", () => {
    expect(getStringAttr({ "llm.model_name": "gpt-4o" }, "llm.model_name")).toBe("gpt-4o");
  });

  it("returns undefined for a missing key", () => {
    expect(getStringAttr({}, "llm.model_name")).toBeUndefined();
  });

  it("returns undefined when value is a number (not a string)", () => {
    expect(getStringAttr({ "x": 42 }, "x")).toBeUndefined();
  });
});

describe("getIntAttr", () => {
  it("returns the integer value when present as number", () => {
    expect(getIntAttr({ "llm.token_count.prompt": 150 }, "llm.token_count.prompt")).toBe(150);
  });

  it("returns 0 for a missing key", () => {
    expect(getIntAttr({}, "llm.token_count.prompt")).toBe(0);
  });

  it("parses a proto3 int64 string (e.g. '85')", () => {
    expect(getIntAttr({ "llm.token_count.completion": "85" }, "llm.token_count.completion")).toBe(85);
  });

  it("returns 0 for a non-numeric string", () => {
    expect(getIntAttr({ "x": "not-a-number" }, "x")).toBe(0);
  });
});

describe("calcLatencyMs", () => {
  it("calculates latency correctly from nanosecond strings", () => {
    // 1.5 seconds = 1_500_000 ms
    const start = "1714000000000000000";
    const end   = "1714000001500000000";
    expect(calcLatencyMs(start, end)).toBe(1500);
  });

  it("returns 0 when timestamps are undefined", () => {
    expect(calcLatencyMs(undefined, undefined)).toBe(0);
  });

  it("returns 0 when end is not greater than start", () => {
    const ts = "1714000000000000000";
    expect(calcLatencyMs(ts, ts)).toBe(0);
  });
});

// ── POST handler integration tests ───────────────────────────────────────────

function makeOtlpRequest(
  overrides: {
    authHeader?: string;
    body?: unknown;
  } = {},
): Request {
  const headers: Record<string, string> = {
    "content-type": "application/json",
  };
  if (overrides.authHeader !== undefined) {
    headers["authorization"] = overrides.authHeader;
  } else {
    // Default: 40-char key that passes length check in validateApiKey
    headers["authorization"] = "Bearer aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
  }

  const body =
    overrides.body !== undefined
      ? JSON.stringify(overrides.body)
      : JSON.stringify({
          resourceSpans: [
            {
              scopeSpans: [
                {
                  spans: [
                    {
                      traceId: "trace-abc",
                      spanId: "span-xyz",
                      name: "ChatCompletions",
                      startTimeUnixNano: "1714000000000000000",
                      endTimeUnixNano: "1714000001500000000",
                      attributes: [
                        { key: "llm.model_name", value: { stringValue: "gpt-4o" } },
                        { key: "llm.token_count.prompt", value: { intValue: 150 } },
                        { key: "llm.token_count.completion", value: { intValue: 85 } },
                        { key: "x-verum-variant", value: { stringValue: "baseline" } },
                        { key: "status_code", value: { stringValue: "OK" } },
                      ],
                    },
                  ],
                },
              ],
            },
          ],
        });

  return new Request("http://localhost/api/v1/otlp/v1/traces", {
    method: "POST",
    headers,
    body,
  });
}

describe("POST /api/v1/otlp/v1/traces", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("returns 401 when Authorization header is missing", async () => {
    const req = makeOtlpRequest({ authHeader: "" });
    const res = await POST(req);
    expect(res.status).toBe(401);
  });

  it("returns 401 when API key is invalid", async () => {
    mockValidateApiKey.mockResolvedValueOnce(null);
    const res = await POST(makeOtlpRequest());
    expect(res.status).toBe(401);
  });

  it("returns 404 when deployment is not found", async () => {
    mockValidateApiKey.mockResolvedValueOnce({ deploymentId: "dep-1", userId: "user-1" });
    mockGetDeployment.mockResolvedValueOnce(null);
    const res = await POST(makeOtlpRequest());
    expect(res.status).toBe(404);
  });

  it("returns 429 when quota is exceeded", async () => {
    mockValidateApiKey.mockResolvedValueOnce({ deploymentId: "dep-1", userId: "user-1" });
    mockGetDeployment.mockResolvedValueOnce({ id: "dep-1" } as never);
    mockCheckQuota.mockResolvedValueOnce({ status: "exceeded", tracesUsed: 1000 });
    const res = await POST(makeOtlpRequest());
    expect(res.status).toBe(429);
  });

  it("returns 202 with partialSuccess for a valid span", async () => {
    mockValidateApiKey.mockResolvedValueOnce({ deploymentId: "dep-1", userId: "user-1" });
    mockGetDeployment.mockResolvedValueOnce({ id: "dep-1" } as never);
    mockCheckQuota.mockResolvedValueOnce({ status: "ok", tracesUsed: 1 });
    mockGetModelPricing.mockResolvedValueOnce({
      input_per_1m_usd: "5.00",
      output_per_1m_usd: "15.00",
    });
    mockInsertTrace.mockResolvedValueOnce("trace-uuid-1");

    const res = await POST(makeOtlpRequest());
    expect(res.status).toBe(202);
    const json = await res.json();
    expect(json).toEqual({ partialSuccess: {} });
  });

  it("calls insertTrace with correct extracted fields including spanAttributes", async () => {
    mockValidateApiKey.mockResolvedValueOnce({ deploymentId: "dep-1", userId: "user-1" });
    mockGetDeployment.mockResolvedValueOnce({ id: "dep-1" } as never);
    mockCheckQuota.mockResolvedValueOnce({ status: "ok", tracesUsed: 1 });
    mockGetModelPricing.mockResolvedValueOnce(null);
    mockInsertTrace.mockResolvedValueOnce("trace-uuid-2");

    await POST(makeOtlpRequest());

    expect(mockInsertTrace).toHaveBeenCalledWith(
      expect.objectContaining({
        model: "gpt-4o",
        inputTokens: 150,
        outputTokens: 85,
        variant: "baseline",
        latencyMs: 1500,
        error: null,
        spanAttributes: expect.objectContaining({ "llm.model_name": "gpt-4o" }),
      }),
    );
  });

  it("returns 202 with empty partialSuccess when resourceSpans is empty", async () => {
    mockValidateApiKey.mockResolvedValueOnce({ deploymentId: "dep-1", userId: "user-1" });
    mockGetDeployment.mockResolvedValueOnce({ id: "dep-1" } as never);

    const res = await POST(
      makeOtlpRequest({ body: { resourceSpans: [] } }),
    );
    expect(res.status).toBe(202);
    expect(mockInsertTrace).not.toHaveBeenCalled();
    expect(mockCheckQuota).not.toHaveBeenCalled();
  });

  it("uses 'unknown' model when llm.model_name attribute is absent", async () => {
    mockValidateApiKey.mockResolvedValueOnce({ deploymentId: "dep-1", userId: "user-1" });
    mockGetDeployment.mockResolvedValueOnce({ id: "dep-1" } as never);
    mockCheckQuota.mockResolvedValueOnce({ status: "ok", tracesUsed: 1 });
    mockGetModelPricing.mockResolvedValueOnce(null);
    mockInsertTrace.mockResolvedValueOnce("trace-uuid-3");

    const noModelBody = {
      resourceSpans: [
        {
          scopeSpans: [
            {
              spans: [
                {
                  startTimeUnixNano: "1714000000000000000",
                  endTimeUnixNano: "1714000001000000000",
                  attributes: [],
                },
              ],
            },
          ],
        },
      ],
    };

    await POST(makeOtlpRequest({ body: noModelBody }));

    expect(mockInsertTrace).toHaveBeenCalledWith(
      expect.objectContaining({ model: "unknown" }),
    );
  });

  it("sets error field when status_code is not OK", async () => {
    mockValidateApiKey.mockResolvedValueOnce({ deploymentId: "dep-1", userId: "user-1" });
    mockGetDeployment.mockResolvedValueOnce({ id: "dep-1" } as never);
    mockCheckQuota.mockResolvedValueOnce({ status: "ok", tracesUsed: 1 });
    mockGetModelPricing.mockResolvedValueOnce(null);
    mockInsertTrace.mockResolvedValueOnce("trace-uuid-4");

    const errorBody = {
      resourceSpans: [
        {
          scopeSpans: [
            {
              spans: [
                {
                  startTimeUnixNano: "1714000000000000000",
                  endTimeUnixNano: "1714000001000000000",
                  attributes: [
                    { key: "llm.model_name", value: { stringValue: "gpt-4o" } },
                    { key: "status_code", value: { stringValue: "ERROR" } },
                  ],
                },
              ],
            },
          ],
        },
      ],
    };

    await POST(makeOtlpRequest({ body: errorBody }));

    expect(mockInsertTrace).toHaveBeenCalledWith(
      expect.objectContaining({ error: "ERROR" }),
    );
  });
});
