import { GET } from "../route";

jest.mock("@/lib/api/handlers", () => ({ getAuthUserId: jest.fn() }));
jest.mock("@/lib/db/queries", () => ({
  getDeployment: jest.fn(),
  getDailyMetrics: jest.fn(),
}));

import { getAuthUserId } from "@/lib/api/handlers";
import { getDeployment, getDailyMetrics } from "@/lib/db/queries";

const mockGetAuthUserId = getAuthUserId as jest.MockedFunction<typeof getAuthUserId>;
const mockGetDeployment = getDeployment as jest.MockedFunction<typeof getDeployment>;
const mockGetDailyMetrics = getDailyMetrics as jest.MockedFunction<typeof getDailyMetrics>;

describe("GET /api/v1/metrics", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("returns 401 if no session", async () => {
    mockGetAuthUserId.mockResolvedValueOnce(null);
    const req = new Request("http://localhost/api/v1/metrics?deployment_id=dep-1");
    const res = await GET(req);
    expect(res.status).toBe(401);
  });

  it("returns 400 if deployment_id is missing", async () => {
    mockGetAuthUserId.mockResolvedValueOnce("user-1");
    const req = new Request("http://localhost/api/v1/metrics");
    const res = await GET(req);
    expect(res.status).toBe(400);
  });

  it("returns 404 if deployment not found", async () => {
    mockGetAuthUserId.mockResolvedValueOnce("user-1");
    mockGetDeployment.mockResolvedValueOnce(null);
    const req = new Request("http://localhost/api/v1/metrics?deployment_id=dep-999");
    const res = await GET(req);
    expect(res.status).toBe(404);
  });

  it("returns 200 with daily metrics on success", async () => {
    mockGetAuthUserId.mockResolvedValueOnce("user-1");
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
