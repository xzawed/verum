import { GET } from "../route";

jest.mock("@/auth", () => ({ auth: jest.fn() }));
jest.mock("@/lib/db/queries", () => ({
  getDeployment: jest.fn(),
  getDailyMetrics: jest.fn(),
}));

import { auth } from "@/auth";
import { getDeployment, getDailyMetrics } from "@/lib/db/queries";

const mockAuth = auth as jest.MockedFunction<typeof auth>;
const mockGetDeployment = getDeployment as jest.MockedFunction<typeof getDeployment>;
const mockGetDailyMetrics = getDailyMetrics as jest.MockedFunction<typeof getDailyMetrics>;

describe("GET /api/v1/metrics", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("returns 401 if no session", async () => {
    mockAuth.mockResolvedValueOnce(null);
    const req = new Request("http://localhost/api/v1/metrics?deployment_id=dep-1");
    const res = await GET(req);
    expect(res.status).toBe(401);
  });

  it("returns 400 if deployment_id is missing", async () => {
    mockAuth.mockResolvedValueOnce({ user: { id: "user-1" } } as never);
    const req = new Request("http://localhost/api/v1/metrics");
    const res = await GET(req);
    expect(res.status).toBe(400);
  });

  it("returns 404 if deployment not found", async () => {
    mockAuth.mockResolvedValueOnce({ user: { id: "user-1" } } as never);
    mockGetDeployment.mockResolvedValueOnce(null);
    const req = new Request("http://localhost/api/v1/metrics?deployment_id=dep-999");
    const res = await GET(req);
    expect(res.status).toBe(404);
  });

  it("returns 200 with daily metrics on success", async () => {
    mockAuth.mockResolvedValueOnce({ user: { id: "user-1" } } as never);
    mockGetDeployment.mockResolvedValueOnce({ id: "dep-1" } as never);
    const metricsData = [
      { date: "2026-04-01", total_cost_usd: 0.05, call_count: 10, p95_latency_ms: 500, avg_judge_score: 0.8 },
    ];
    mockGetDailyMetrics.mockResolvedValueOnce(metricsData as never);
    const req = new Request("http://localhost/api/v1/metrics?deployment_id=dep-1&days=7");
    const res = await GET(req);
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body).toMatchObject({ daily: metricsData });
  });
});
