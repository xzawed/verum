import { GET } from "../route";

jest.mock("@/auth", () => ({ auth: jest.fn() }));
jest.mock("@/lib/db/queries", () => ({
  getDeployment: jest.fn(),
  getExperiments: jest.fn(),
}));

import { auth } from "@/auth";
import { getDeployment, getExperiments } from "@/lib/db/queries";

const mockAuth = auth as jest.MockedFunction<typeof auth>;
const mockGetDeployment = getDeployment as jest.MockedFunction<typeof getDeployment>;
const mockGetExperiments = getExperiments as jest.MockedFunction<typeof getExperiments>;

describe("GET /api/v1/experiments", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("returns 401 if no session", async () => {
    mockAuth.mockResolvedValueOnce(null);
    const req = new Request("http://localhost/api/v1/experiments?deployment_id=dep-1");
    const res = await GET(req);
    expect(res.status).toBe(401);
  });

  it("returns 400 if deployment_id param is missing", async () => {
    mockAuth.mockResolvedValueOnce({ user: { id: "user-1" } } as never);
    const req = new Request("http://localhost/api/v1/experiments");
    const res = await GET(req);
    expect(res.status).toBe(400);
  });

  it("returns 404 if deployment not found", async () => {
    mockAuth.mockResolvedValueOnce({ user: { id: "user-1" } } as never);
    mockGetDeployment.mockResolvedValueOnce(null);
    const req = new Request("http://localhost/api/v1/experiments?deployment_id=dep-999");
    const res = await GET(req);
    expect(res.status).toBe(404);
  });

  it("returns 200 with experiments on success", async () => {
    mockAuth.mockResolvedValueOnce({ user: { id: "user-1" } } as never);
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
