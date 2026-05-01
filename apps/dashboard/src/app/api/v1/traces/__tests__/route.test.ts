jest.mock("@/lib/rateLimit", () => ({
  checkRateLimitDual: jest.fn().mockResolvedValue(null),
  getClientIp: jest.fn().mockReturnValue("127.0.0.1"),
}));

import { GET, POST } from "../route";

jest.mock("@/auth", () => ({ auth: jest.fn() }));
jest.mock("@/lib/db/queries", () => ({
  getDeployment: jest.fn(),
  getTraceList: jest.fn(),
}));
jest.mock("@/lib/db/jobs", () => ({
  getModelPricing: jest.fn(),
  insertTrace: jest.fn(),
}));
jest.mock("@/lib/api/validateApiKey", () => ({
  validateApiKey: jest.fn(),
}));
jest.mock("@/lib/db/quota", () => ({
  checkAndIncrementTraceQuota: jest.fn(),
  FREE_LIMITS: { traces: 1000 },
}));

import { auth } from "@/auth";
import { getDeployment, getTraceList } from "@/lib/db/queries";
import { getModelPricing, insertTrace } from "@/lib/db/jobs";
import { validateApiKey } from "@/lib/api/validateApiKey";
import { checkAndIncrementTraceQuota } from "@/lib/db/quota";
import { checkRateLimitDual } from "@/lib/rateLimit";

const mockAuth = auth as jest.MockedFunction<typeof auth>;
const mockGetDeployment = getDeployment as jest.Mock;
const mockGetTraceList = getTraceList as jest.Mock;
const mockGetModelPricing = getModelPricing as jest.Mock;
const mockInsertTrace = insertTrace as jest.Mock;
const mockValidateApiKey = validateApiKey as jest.Mock;
const mockCheckAndIncrementTraceQuota = checkAndIncrementTraceQuota as jest.Mock;
const mockCheckRateLimitDual = checkRateLimitDual as jest.Mock;

describe("GET /api/v1/traces", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("returns 401 if no session", async () => {
    mockAuth.mockResolvedValueOnce(null);
    const req = new Request("http://localhost/api/v1/traces?deployment_id=abc");
    const res = await GET(req);
    expect(res.status).toBe(401);
  });

  it("returns 400 if deployment_id is missing", async () => {
    mockAuth.mockResolvedValueOnce({ user: { id: "user-1" } } as never);
    const req = new Request("http://localhost/api/v1/traces");
    const res = await GET(req);
    expect(res.status).toBe(400);
  });

  it("returns 404 if deployment not found", async () => {
    mockAuth.mockResolvedValueOnce({ user: { id: "user-1" } } as never);
    mockGetDeployment.mockResolvedValueOnce(null);
    const req = new Request("http://localhost/api/v1/traces?deployment_id=dep-999");
    const res = await GET(req);
    expect(res.status).toBe(404);
  });

  it("returns 200 with traces, total, page on success", async () => {
    mockAuth.mockResolvedValueOnce({ user: { id: "user-1" } } as never);
    mockGetDeployment.mockResolvedValueOnce({ id: "dep-1" } as never);
    mockGetTraceList.mockResolvedValueOnce({
      traces: [{ id: "trace-1", variant: "baseline" }],
      total: 1,
      page: 1,
    });
    const req = new Request("http://localhost/api/v1/traces?deployment_id=dep-1");
    const res = await GET(req);
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(Array.isArray(body.traces)).toBe(true);
    expect(body.total).toBe(1);
    expect(body.page).toBe(1);
  });
});

// ---------------------------------------------------------------------------
// Helpers for POST tests
// ---------------------------------------------------------------------------

function makePostReq(body: object, apiKey = "valid-api-key-123") {
  return new Request("http://localhost/api/v1/traces", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-verum-api-key": apiKey,
    },
    body: JSON.stringify(body),
  });
}

const defaultBody = {
  deployment_id: "00000000-0000-0000-0000-000000000001",
  variant: "baseline",
  model: "gpt-4",
  input_tokens: 100,
  output_tokens: 50,
  latency_ms: 300,
  error: null,
};

describe("POST /api/v1/traces", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // checkRateLimitDual default: no rate-limit (pass through)
    mockCheckRateLimitDual.mockResolvedValue(null);
  });

  it("returns 401 when x-verum-api-key header is absent", async () => {
    const req = new Request("http://localhost/api/v1/traces", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(defaultBody),
    });
    const res = await POST(req);
    expect(res.status).toBe(401);
  });

  it("passes through rate-limit Response when rate limit is hit", async () => {
    const rateLimitResponse = new Response("rate limit exceeded", { status: 429 });
    mockCheckRateLimitDual.mockResolvedValueOnce(rateLimitResponse);
    const res = await POST(makePostReq(defaultBody));
    expect(res.status).toBe(429);
  });

  it("returns 400 when model is missing from body", async () => {
    const body = { ...defaultBody, model: "" };
    const res = await POST(makePostReq(body));
    expect(res.status).toBe(400);
  });

  it("returns 400 when model field exceeds 200 characters", async () => {
    const body = { ...defaultBody, model: "m".repeat(201) };
    const res = await POST(makePostReq(body));
    expect(res.status).toBe(400);
  });

  it("returns 401 when validateApiKey returns null", async () => {
    mockValidateApiKey.mockResolvedValueOnce(null);
    const res = await POST(makePostReq(defaultBody));
    expect(res.status).toBe(401);
  });

  it("returns 404 when deployment is not found", async () => {
    mockValidateApiKey.mockResolvedValueOnce({ deploymentId: "dep-1", userId: "user-1" });
    mockGetDeployment.mockResolvedValueOnce(null);
    const res = await POST(makePostReq(defaultBody));
    expect(res.status).toBe(404);
  });

  it("returns 429 when trace quota is exceeded", async () => {
    mockValidateApiKey.mockResolvedValueOnce({ deploymentId: "dep-1", userId: "user-1" });
    mockGetDeployment.mockResolvedValueOnce({ id: "dep-1" });
    mockCheckAndIncrementTraceQuota.mockResolvedValueOnce({ status: "exceeded", tracesUsed: 1000 });
    const res = await POST(makePostReq(defaultBody));
    expect(res.status).toBe(429);
  });

  it("returns 201 and emits console.warn when quota is in warning state", async () => {
    mockValidateApiKey.mockResolvedValueOnce({ deploymentId: "dep-1", userId: "user-1" });
    mockGetDeployment.mockResolvedValueOnce({ id: "dep-1" });
    mockCheckAndIncrementTraceQuota.mockResolvedValueOnce({ status: "warning", tracesUsed: 900 });
    mockGetModelPricing.mockResolvedValueOnce(null);
    mockInsertTrace.mockResolvedValueOnce("trace-999");
    const warnSpy = jest.spyOn(console, "warn").mockImplementation(() => {});
    const res = await POST(makePostReq(defaultBody));
    expect(res.status).toBe(201);
    expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining("QUOTA WARNING"));
    warnSpy.mockRestore();
  });

  it("returns 201 with costUsd = '0' when no pricing is found", async () => {
    mockValidateApiKey.mockResolvedValueOnce({ deploymentId: "dep-1", userId: "user-1" });
    mockGetDeployment.mockResolvedValueOnce({ id: "dep-1" });
    mockCheckAndIncrementTraceQuota.mockResolvedValueOnce({ status: "ok", tracesUsed: 10 });
    mockGetModelPricing.mockResolvedValueOnce(null);
    mockInsertTrace.mockResolvedValueOnce("trace-abc");

    const res = await POST(makePostReq(defaultBody));
    expect(res.status).toBe(201);
    const body = await res.json();
    expect(body.trace_id).toBe("trace-abc");
    // insertTrace should have been called with costUsd = "0"
    expect(mockInsertTrace).toHaveBeenCalledWith(
      expect.objectContaining({ costUsd: "0" })
    );
  });

  it("uses VERUM_TRACE_RATE_LIMIT_PER_KEY env var as per-key limit", async () => {
    const origKey = process.env.VERUM_TRACE_RATE_LIMIT_PER_KEY;
    process.env.VERUM_TRACE_RATE_LIMIT_PER_KEY = "500";
    try {
      mockValidateApiKey.mockResolvedValueOnce({ deploymentId: "dep-1", userId: "user-1" });
      mockGetDeployment.mockResolvedValueOnce({ id: "dep-1" });
      mockCheckAndIncrementTraceQuota.mockResolvedValueOnce({ status: "ok", tracesUsed: 5 });
      mockGetModelPricing.mockResolvedValueOnce(null);
      mockInsertTrace.mockResolvedValueOnce("trace-env-key");

      await POST(makePostReq(defaultBody));

      expect(mockCheckRateLimitDual).toHaveBeenCalledWith(
        expect.any(String),
        500,
        expect.any(String),
        200,
      );
    } finally {
      if (origKey === undefined) delete process.env.VERUM_TRACE_RATE_LIMIT_PER_KEY;
      else process.env.VERUM_TRACE_RATE_LIMIT_PER_KEY = origKey;
    }
  });

  it("uses VERUM_TRACE_RATE_LIMIT_PER_IP env var as per-IP limit", async () => {
    const origIp = process.env.VERUM_TRACE_RATE_LIMIT_PER_IP;
    process.env.VERUM_TRACE_RATE_LIMIT_PER_IP = "1000";
    try {
      mockValidateApiKey.mockResolvedValueOnce({ deploymentId: "dep-1", userId: "user-1" });
      mockGetDeployment.mockResolvedValueOnce({ id: "dep-1" });
      mockCheckAndIncrementTraceQuota.mockResolvedValueOnce({ status: "ok", tracesUsed: 5 });
      mockGetModelPricing.mockResolvedValueOnce(null);
      mockInsertTrace.mockResolvedValueOnce("trace-env-ip");

      await POST(makePostReq(defaultBody));

      expect(mockCheckRateLimitDual).toHaveBeenCalledWith(
        expect.any(String),
        120,
        expect.any(String),
        1000,
      );
    } finally {
      if (origIp === undefined) delete process.env.VERUM_TRACE_RATE_LIMIT_PER_IP;
      else process.env.VERUM_TRACE_RATE_LIMIT_PER_IP = origIp;
    }
  });

  it("falls back to 120/200 defaults when env vars parse to NaN", async () => {
    const origKey = process.env.VERUM_TRACE_RATE_LIMIT_PER_KEY;
    const origIp = process.env.VERUM_TRACE_RATE_LIMIT_PER_IP;
    process.env.VERUM_TRACE_RATE_LIMIT_PER_KEY = "invalid";
    process.env.VERUM_TRACE_RATE_LIMIT_PER_IP = "bad";
    try {
      mockValidateApiKey.mockResolvedValueOnce({ deploymentId: "dep-1", userId: "user-1" });
      mockGetDeployment.mockResolvedValueOnce({ id: "dep-1" });
      mockCheckAndIncrementTraceQuota.mockResolvedValueOnce({ status: "ok", tracesUsed: 5 });
      mockGetModelPricing.mockResolvedValueOnce(null);
      mockInsertTrace.mockResolvedValueOnce("trace-fallback");

      await POST(makePostReq(defaultBody));

      expect(mockCheckRateLimitDual).toHaveBeenCalledWith(
        expect.any(String),
        120,
        expect.any(String),
        200,
      );
    } finally {
      if (origKey === undefined) delete process.env.VERUM_TRACE_RATE_LIMIT_PER_KEY;
      else process.env.VERUM_TRACE_RATE_LIMIT_PER_KEY = origKey;
      if (origIp === undefined) delete process.env.VERUM_TRACE_RATE_LIMIT_PER_IP;
      else process.env.VERUM_TRACE_RATE_LIMIT_PER_IP = origIp;
    }
  });

  it("returns 201 with correctly calculated cost when pricing is found", async () => {
    mockValidateApiKey.mockResolvedValueOnce({ deploymentId: "dep-1", userId: "user-1" });
    mockGetDeployment.mockResolvedValueOnce({ id: "dep-1" });
    mockCheckAndIncrementTraceQuota.mockResolvedValueOnce({ status: "ok", tracesUsed: 5 });
    // input_per_1m_usd = 3, output_per_1m_usd = 6
    mockGetModelPricing.mockResolvedValueOnce({
      input_per_1m_usd: "3",
      output_per_1m_usd: "6",
    });
    mockInsertTrace.mockResolvedValueOnce("trace-xyz");

    // body: input_tokens=1000000, output_tokens=1000000 → inputCost=3, outputCost=6 → total=9
    const body = {
      ...defaultBody,
      input_tokens: 1_000_000,
      output_tokens: 1_000_000,
    };
    const res = await POST(makePostReq(body));
    expect(res.status).toBe(201);
    const resBody = await res.json();
    expect(resBody.trace_id).toBe("trace-xyz");
    expect(mockInsertTrace).toHaveBeenCalledWith(
      expect.objectContaining({ costUsd: "9.000000" })
    );
  });
});
