import { GET } from "../route";

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

const mockAuth = auth as jest.MockedFunction<typeof auth>;
const mockGetDeployment = getDeployment as jest.MockedFunction<typeof getDeployment>;
const mockGetTraceList = getTraceList as jest.MockedFunction<typeof getTraceList>;

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
