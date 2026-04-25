jest.mock("@/lib/rateLimit", () => ({
  checkRateLimit: jest.fn().mockResolvedValue(null),
}));
jest.mock("@/auth", () => ({ auth: jest.fn() }));
jest.mock("@/lib/db/jobs", () => ({
  rollbackDeployment: jest.fn(),
}));
jest.mock("@/lib/db/queries", () => ({
  getDeployment: jest.fn(),
}));

import { POST } from "../route";
import { auth } from "@/auth";
import { rollbackDeployment } from "@/lib/db/jobs";
import { getDeployment } from "@/lib/db/queries";

const mockAuth = auth as jest.MockedFunction<typeof auth>;
const mockRollbackDeployment = rollbackDeployment as jest.MockedFunction<
  typeof rollbackDeployment
>;
const mockGetDeployment = getDeployment as jest.MockedFunction<typeof getDeployment>;

function makeRequest(): Request {
  return new Request("http://localhost/api/v1/deploy/dep-1/rollback", {
    method: "POST",
  });
}

beforeEach(() => {
  jest.clearAllMocks();
});

describe("POST /api/v1/deploy/[id]/rollback", () => {
  it("returns 401 when there is no session", async () => {
    mockAuth.mockResolvedValueOnce(null);
    const req = makeRequest();
    const res = await POST(req, { params: Promise.resolve({ id: "dep-1" }) });
    expect(res.status).toBe(401);
  });

  it("returns 404 when deployment is not found", async () => {
    mockAuth.mockResolvedValueOnce({ user: { id: "user-1" } } as never);
    mockGetDeployment.mockResolvedValueOnce(null);
    const req = makeRequest();
    const res = await POST(req, { params: Promise.resolve({ id: "dep-missing" }) });
    expect(res.status).toBe(404);
  });

  it("returns 200 with status:rolled_back on success", async () => {
    mockAuth.mockResolvedValueOnce({ user: { id: "user-1" } } as never);
    mockGetDeployment.mockResolvedValueOnce({ id: "dep-1" } as never);
    mockRollbackDeployment.mockResolvedValueOnce(undefined as never);

    const req = makeRequest();
    const res = await POST(req, { params: Promise.resolve({ id: "dep-1" }) });
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body).toEqual({ status: "rolled_back" });
    expect(mockRollbackDeployment).toHaveBeenCalledWith("user-1", "dep-1");
  });
});
