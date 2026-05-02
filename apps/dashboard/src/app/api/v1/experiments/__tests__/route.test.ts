import { GET } from "../route";

jest.mock("@/lib/api/handlers", () => ({ getAuthUserId: jest.fn() }));
jest.mock("@/lib/db/queries", () => ({
  getDeployment: jest.fn(),
  getExperiments: jest.fn(),
}));

import { getAuthUserId } from "@/lib/api/handlers";
import { getDeployment, getExperiments } from "@/lib/db/queries";

const mockGetAuthUserId = getAuthUserId as jest.MockedFunction<typeof getAuthUserId>;
const mockGetDeployment = getDeployment as jest.MockedFunction<typeof getDeployment>;
const mockGetExperiments = getExperiments as jest.MockedFunction<typeof getExperiments>;

describe("GET /api/v1/experiments", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("returns 401 if no session", async () => {
    mockGetAuthUserId.mockResolvedValueOnce(null);
    const req = new Request("http://localhost/api/v1/experiments?deployment_id=dep-1");
    const res = await GET(req);
    expect(res.status).toBe(401);
  });

  it("returns 400 if deployment_id param is missing", async () => {
    mockGetAuthUserId.mockResolvedValueOnce("user-1");
    const req = new Request("http://localhost/api/v1/experiments");
    const res = await GET(req);
    expect(res.status).toBe(400);
  });

  it("returns 404 if deployment not found", async () => {
    mockGetAuthUserId.mockResolvedValueOnce("user-1");
    mockGetDeployment.mockResolvedValueOnce(null);
    const req = new Request("http://localhost/api/v1/experiments?deployment_id=dep-999");
    const res = await GET(req);
    expect(res.status).toBe(404);
  });

  it("returns 200 with experiments on success", async () => {
    mockGetAuthUserId.mockResolvedValueOnce("user-1");
    mockGetDeployment.mockResolvedValueOnce({ id: "dep-1" } as never);
    mockGetExperiments.mockResolvedValueOnce([
      { id: "exp-1", status: "running", deployment_id: "dep-1" } as never,
      { id: "exp-2", status: "done", deployment_id: "dep-1" } as never,
    ]);
    const req = new Request("http://localhost/api/v1/experiments?deployment_id=dep-1");
    const res = await GET(req);
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.experiments).toHaveLength(2);
    expect(body.current_experiment).toMatchObject({ id: "exp-1", status: "running" });
  });
});
