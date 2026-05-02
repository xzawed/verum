jest.mock("@/lib/api/handlers", () => ({ getAuthUserId: jest.fn() }));
jest.mock("@/lib/db/client", () => ({
  db: {
    select: jest.fn().mockReturnValue({
      from: jest.fn().mockReturnValue({
        where: jest.fn().mockReturnValue({
          orderBy: jest.fn().mockResolvedValue([]),
          limit: jest.fn().mockResolvedValue([]),
        }),
      }),
    }),
    insert: jest.fn().mockReturnValue({
      values: jest.fn().mockReturnValue({
        returning: jest.fn().mockResolvedValue([{ id: "int-1" }]),
      }),
    }),
    update: jest.fn().mockReturnValue({
      set: jest.fn().mockReturnValue({
        where: jest.fn().mockResolvedValue([]),
      }),
    }),
  },
}));
jest.mock("@/lib/encrypt", () => ({
  encrypt: jest.fn((s: string) => `enc:${s}`),
  decrypt: jest.fn((s: string) => s.replace("enc:", "")),
}));
jest.mock("@/lib/railway", () => ({
  listRailwayServices: jest.fn().mockResolvedValue([]),
  upsertRailwayVariables: jest.fn().mockResolvedValue(undefined),
  deleteRailwayVariables: jest.fn().mockResolvedValue(undefined),
}));

import { getAuthUserId } from "@/lib/api/handlers";
import { db } from "@/lib/db/client";
import { upsertRailwayVariables, deleteRailwayVariables } from "@/lib/railway";
import { GET, POST } from "../route";
import { GET as GET_SERVICES } from "../railway/services/route";
import { POST as POST_DISCONNECT } from "../[id]/disconnect/route";

const mockGetAuthUserId = getAuthUserId as jest.MockedFunction<typeof getAuthUserId>;
const mockDb = db as jest.Mocked<typeof db>;
const mockUpsertRailwayVariables = upsertRailwayVariables as jest.MockedFunction<typeof upsertRailwayVariables>;
const mockDeleteRailwayVariables = deleteRailwayVariables as jest.MockedFunction<typeof deleteRailwayVariables>;

function makeSession(userId = "user-1") {
  return userId;
}

function makePostRequest(body: unknown, url = "http://localhost/api/integrations"): Request {
  return new Request(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

const VALID_BODY = {
  railway_token: "tok_123",
  project_id: "proj-1",
  service_id: "svc-1",
  environment_id: "env-1",
  service_name: "my-service",
};

beforeEach(() => {
  jest.clearAllMocks();
});

// ─── GET /api/integrations ────────────────────────────────────────────────────

describe("GET /api/integrations", () => {
  it("returns 401 without session", async () => {
    mockGetAuthUserId.mockResolvedValueOnce(null);
    const res = await GET(new Request("http://localhost/api/integrations"));
    expect(res.status).toBe(401);
  });

  it("returns 200 with empty integrations array", async () => {
    mockGetAuthUserId.mockResolvedValueOnce(makeSession());
    const orderByMock = jest.fn().mockResolvedValue([]);
    (mockDb.select as jest.Mock).mockReturnValueOnce({
      from: jest.fn().mockReturnValue({
        where: jest.fn().mockReturnValue({
          orderBy: orderByMock,
        }),
      }),
    });
    const res = await GET(new Request("http://localhost/api/integrations"));
    expect(res.status).toBe(200);
    const body = (await res.json()) as { integrations: unknown[] };
    expect(body.integrations).toHaveLength(0);
  });

  it("returns integrations without platform_token_encrypted", async () => {
    mockGetAuthUserId.mockResolvedValueOnce(makeSession());
    // Simulate what Drizzle returns when selecting only specific columns:
    // platform_token_encrypted is NOT selected, so it won't appear in the row.
    const row = {
      id: "int-1",
      user_id: "user-1",
      status: "connected",
      created_at: new Date("2026-01-01"),
    };
    (mockDb.select as jest.Mock).mockReturnValueOnce({
      from: jest.fn().mockReturnValue({
        where: jest.fn().mockReturnValue({
          orderBy: jest.fn().mockResolvedValue([row]),
        }),
      }),
    });
    const res = await GET(new Request("http://localhost/api/integrations"));
    expect(res.status).toBe(200);
    const body = (await res.json()) as { integrations: Record<string, unknown>[] };
    expect(body.integrations).toHaveLength(1);
    expect(body.integrations[0]).not.toHaveProperty("platform_token_encrypted");
    expect(body.integrations[0].id).toBe("int-1");
  });
});

// ─── POST /api/integrations ───────────────────────────────────────────────────

describe("POST /api/integrations", () => {
  it("returns 401 without session", async () => {
    mockGetAuthUserId.mockResolvedValueOnce(null);
    const res = await POST(makePostRequest(VALID_BODY));
    expect(res.status).toBe(401);
  });

  it("returns 400 for missing required fields", async () => {
    mockGetAuthUserId.mockResolvedValueOnce(makeSession());
    const res = await POST(makePostRequest({ railway_token: "tok" }));
    expect(res.status).toBe(400);
  });

  it("returns 400 for empty railway_token", async () => {
    mockGetAuthUserId.mockResolvedValueOnce(makeSession());
    const res = await POST(makePostRequest({ ...VALID_BODY, railway_token: "" }));
    expect(res.status).toBe(400);
  });

  it("returns 201 and integration_id on success", async () => {
    mockGetAuthUserId.mockResolvedValueOnce(makeSession());
    mockUpsertRailwayVariables.mockResolvedValueOnce(undefined);
    (mockDb.insert as jest.Mock).mockReturnValueOnce({
      values: jest.fn().mockReturnValue({
        returning: jest.fn().mockResolvedValue([{ id: "int-1" }]),
      }),
    });
    const res = await POST(makePostRequest(VALID_BODY));
    expect(res.status).toBe(201);
    const body = (await res.json()) as { integration_id: string };
    expect(body.integration_id).toBe("int-1");
  });

  it("injects NODE_OPTIONS when inject_node_options is true", async () => {
    mockGetAuthUserId.mockResolvedValueOnce(makeSession());
    mockUpsertRailwayVariables.mockResolvedValueOnce(undefined);
    (mockDb.insert as jest.Mock).mockReturnValueOnce({
      values: jest.fn().mockReturnValue({
        returning: jest.fn().mockResolvedValue([{ id: "int-2" }]),
      }),
    });
    const res = await POST(makePostRequest({ ...VALID_BODY, inject_node_options: true }));
    expect(res.status).toBe(201);
    expect(mockUpsertRailwayVariables).toHaveBeenCalledWith(
      "tok_123",
      "proj-1",
      "svc-1",
      "env-1",
      expect.objectContaining({
        NODE_OPTIONS: "--require @opentelemetry/auto-instrumentations-node/register",
      }),
    );
  });

  it("does not inject NODE_OPTIONS when inject_node_options is false", async () => {
    mockGetAuthUserId.mockResolvedValueOnce(makeSession());
    mockUpsertRailwayVariables.mockResolvedValueOnce(undefined);
    (mockDb.insert as jest.Mock).mockReturnValueOnce({
      values: jest.fn().mockReturnValue({
        returning: jest.fn().mockResolvedValue([{ id: "int-3" }]),
      }),
    });
    const res = await POST(makePostRequest({ ...VALID_BODY, inject_node_options: false }));
    expect(res.status).toBe(201);
    const calledVars = mockUpsertRailwayVariables.mock.calls[0][4] as Record<string, string>;
    expect(calledVars).not.toHaveProperty("NODE_OPTIONS");
  });

  it("always injects OTEL_EXPORTER_OTLP_TRACES_ENDPOINT and protocol", async () => {
    mockGetAuthUserId.mockResolvedValueOnce(makeSession());
    mockUpsertRailwayVariables.mockResolvedValueOnce(undefined);
    (mockDb.insert as jest.Mock).mockReturnValueOnce({
      values: jest.fn().mockReturnValue({
        returning: jest.fn().mockResolvedValue([{ id: "int-4" }]),
      }),
    });
    const res = await POST(makePostRequest(VALID_BODY));
    expect(res.status).toBe(201);
    const calledVars = mockUpsertRailwayVariables.mock.calls[0][4] as Record<string, string>;
    expect(calledVars).not.toHaveProperty("OTEL_EXPORTER_OTLP_ENDPOINT");
    expect(calledVars["OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"]).toMatch(/\/api\/v1\/otlp\/v1\/traces$/);
    expect(calledVars["OTEL_EXPORTER_OTLP_PROTOCOL"]).toBe("http/json");
  });

  it("injects OTEL_EXPORTER_OTLP_HEADERS when verum_api_key is provided", async () => {
    mockGetAuthUserId.mockResolvedValueOnce(makeSession());
    mockUpsertRailwayVariables.mockResolvedValueOnce(undefined);
    (mockDb.insert as jest.Mock).mockReturnValueOnce({
      values: jest.fn().mockReturnValue({
        returning: jest.fn().mockResolvedValue([{ id: "int-5" }]),
      }),
    });
    const apiKey = "vk_" + "a".repeat(64);
    const res = await POST(makePostRequest({ ...VALID_BODY, verum_api_key: apiKey }));
    expect(res.status).toBe(201);
    const calledVars = mockUpsertRailwayVariables.mock.calls[0][4] as Record<string, string>;
    expect(calledVars["OTEL_EXPORTER_OTLP_HEADERS"]).toBe(`Authorization=Bearer ${apiKey}`);
  });

  it("does not inject OTEL_EXPORTER_OTLP_HEADERS when verum_api_key is absent", async () => {
    mockGetAuthUserId.mockResolvedValueOnce(makeSession());
    mockUpsertRailwayVariables.mockResolvedValueOnce(undefined);
    (mockDb.insert as jest.Mock).mockReturnValueOnce({
      values: jest.fn().mockReturnValue({
        returning: jest.fn().mockResolvedValue([{ id: "int-6" }]),
      }),
    });
    const res = await POST(makePostRequest(VALID_BODY));
    expect(res.status).toBe(201);
    const calledVars = mockUpsertRailwayVariables.mock.calls[0][4] as Record<string, string>;
    expect(calledVars).not.toHaveProperty("OTEL_EXPORTER_OTLP_HEADERS");
  });

  it("returns 502 when upsertRailwayVariables throws", async () => {
    mockGetAuthUserId.mockResolvedValueOnce(makeSession());
    mockUpsertRailwayVariables.mockRejectedValueOnce(new Error("Railway down"));
    const res = await POST(makePostRequest(VALID_BODY));
    expect(res.status).toBe(502);
  });

  it("returns 404 when repo_id provided but not owned by user", async () => {
    mockGetAuthUserId.mockResolvedValueOnce(makeSession());
    // repo ownership check returns empty
    (mockDb.select as jest.Mock).mockReturnValueOnce({
      from: jest.fn().mockReturnValue({
        where: jest.fn().mockReturnValue({
          limit: jest.fn().mockResolvedValue([]),
        }),
      }),
    });
    const res = await POST(makePostRequest({ ...VALID_BODY, repo_id: "11111111-1111-1111-1111-111111111111" }));
    expect(res.status).toBe(404);
  });
});

// ─── POST /api/integrations/[id]/disconnect ───────────────────────────────────

describe("POST /api/integrations/[id]/disconnect", () => {
  function makeCtx(id: string) {
    return { params: Promise.resolve({ id }) };
  }

  it("returns 401 without session", async () => {
    mockGetAuthUserId.mockResolvedValueOnce(null);
    const res = await POST_DISCONNECT(
      new Request("http://localhost/api/integrations/int-1/disconnect", { method: "POST" }),
      makeCtx("int-1"),
    );
    expect(res.status).toBe(401);
  });

  it("returns 404 when integration not found", async () => {
    mockGetAuthUserId.mockResolvedValueOnce(makeSession());
    (mockDb.select as jest.Mock).mockReturnValueOnce({
      from: jest.fn().mockReturnValue({
        where: jest.fn().mockReturnValue({
          limit: jest.fn().mockResolvedValue([]),
        }),
      }),
    });
    const res = await POST_DISCONNECT(
      new Request("http://localhost/api/integrations/no-such/disconnect", { method: "POST" }),
      makeCtx("no-such"),
    );
    expect(res.status).toBe(404);
  });

  it("returns 200 and success: true on disconnect (no credentials)", async () => {
    mockGetAuthUserId.mockResolvedValueOnce(makeSession());
    (mockDb.select as jest.Mock).mockReturnValueOnce({
      from: jest.fn().mockReturnValue({
        where: jest.fn().mockReturnValue({
          limit: jest.fn().mockResolvedValue([
            {
              id: "int-1",
              platform_token_encrypted: null,
              platform_project_id: null,
              platform_service_id: null,
              platform_environment_id: null,
              injected_vars: {},
            },
          ]),
        }),
      }),
    });
    (mockDb.update as jest.Mock).mockReturnValueOnce({
      set: jest.fn().mockReturnValue({
        where: jest.fn().mockResolvedValue([]),
      }),
    });
    const res = await POST_DISCONNECT(
      new Request("http://localhost/api/integrations/int-1/disconnect", { method: "POST" }),
      makeCtx("int-1"),
    );
    expect(res.status).toBe(200);
    const body = (await res.json()) as { success: boolean };
    expect(body.success).toBe(true);
  });

  it("calls deleteRailwayVariables when credentials are present", async () => {
    mockGetAuthUserId.mockResolvedValueOnce(makeSession());
    mockDeleteRailwayVariables.mockResolvedValueOnce(undefined);
    (mockDb.select as jest.Mock).mockReturnValueOnce({
      from: jest.fn().mockReturnValue({
        where: jest.fn().mockReturnValue({
          limit: jest.fn().mockResolvedValue([
            {
              id: "int-1",
              platform_token_encrypted: "enc:tok_123",
              platform_project_id: "proj-1",
              platform_service_id: "svc-1",
              platform_environment_id: "env-1",
              injected_vars: { OTEL_EXPORTER_OTLP_ENDPOINT: "https://example.com/otlp" },
            },
          ]),
        }),
      }),
    });
    (mockDb.update as jest.Mock).mockReturnValueOnce({
      set: jest.fn().mockReturnValue({
        where: jest.fn().mockResolvedValue([]),
      }),
    });
    const res = await POST_DISCONNECT(
      new Request("http://localhost/api/integrations/int-1/disconnect", { method: "POST" }),
      makeCtx("int-1"),
    );
    expect(res.status).toBe(200);
    expect(mockDeleteRailwayVariables).toHaveBeenCalledWith(
      "tok_123",
      "proj-1",
      "svc-1",
      "env-1",
      ["OTEL_EXPORTER_OTLP_ENDPOINT"],
    );
  });

  it("still returns 200 when deleteRailwayVariables throws (best-effort)", async () => {
    mockGetAuthUserId.mockResolvedValueOnce(makeSession());
    mockDeleteRailwayVariables.mockRejectedValueOnce(new Error("Railway down"));
    (mockDb.select as jest.Mock).mockReturnValueOnce({
      from: jest.fn().mockReturnValue({
        where: jest.fn().mockReturnValue({
          limit: jest.fn().mockResolvedValue([
            {
              id: "int-1",
              platform_token_encrypted: "enc:tok_123",
              platform_project_id: "proj-1",
              platform_service_id: "svc-1",
              platform_environment_id: "env-1",
              injected_vars: { OTEL_EXPORTER_OTLP_ENDPOINT: "https://example.com/otlp" },
            },
          ]),
        }),
      }),
    });
    (mockDb.update as jest.Mock).mockReturnValueOnce({
      set: jest.fn().mockReturnValue({
        where: jest.fn().mockResolvedValue([]),
      }),
    });
    const res = await POST_DISCONNECT(
      new Request("http://localhost/api/integrations/int-1/disconnect", { method: "POST" }),
      makeCtx("int-1"),
    );
    expect(res.status).toBe(200);
    const body = (await res.json()) as { success: boolean };
    expect(body.success).toBe(true);
  });
});

// ─── GET /api/integrations/railway/services ───────────────────────────────────

describe("GET /api/integrations/railway/services", () => {
  it("returns 401 without session", async () => {
    mockGetAuthUserId.mockResolvedValueOnce(null);
    const res = await GET_SERVICES(new Request("http://localhost/api/integrations/railway/services?token=tok"));
    expect(res.status).toBe(401);
  });

  it("returns 400 when token param is missing", async () => {
    mockGetAuthUserId.mockResolvedValueOnce(makeSession());
    const res = await GET_SERVICES(new Request("http://localhost/api/integrations/railway/services"));
    expect(res.status).toBe(400);
  });

  it("returns 200 with services list", async () => {
    mockGetAuthUserId.mockResolvedValueOnce(makeSession());
    const { listRailwayServices } = jest.requireMock("@/lib/railway") as { listRailwayServices: jest.Mock };
    listRailwayServices.mockResolvedValueOnce([{ id: "svc-1", name: "my-service" }]);
    const res = await GET_SERVICES(new Request("http://localhost/api/integrations/railway/services?token=tok"));
    expect(res.status).toBe(200);
    const body = (await res.json()) as { services: unknown[] };
    expect(body.services).toHaveLength(1);
  });

  it("returns 502 when listRailwayServices throws", async () => {
    mockGetAuthUserId.mockResolvedValueOnce(makeSession());
    const { listRailwayServices } = jest.requireMock("@/lib/railway") as { listRailwayServices: jest.Mock };
    listRailwayServices.mockRejectedValueOnce(new Error("Railway API error"));
    const res = await GET_SERVICES(new Request("http://localhost/api/integrations/railway/services?token=bad"));
    expect(res.status).toBe(502);
  });
});
