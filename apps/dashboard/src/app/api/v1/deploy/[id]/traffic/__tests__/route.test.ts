jest.mock("@/lib/api/handlers", () => ({ getAuthUserId: jest.fn() }));
jest.mock("@/lib/db/jobs", () => ({
  updateDeploymentTraffic: jest.fn(),
}));
jest.mock("@/lib/db/queries", () => ({
  getDeployment: jest.fn(),
}));

import { PATCH } from "../route";
import { getAuthUserId } from "@/lib/api/handlers";
import { updateDeploymentTraffic } from "@/lib/db/jobs";
import { getDeployment } from "@/lib/db/queries";

const mockGetAuthUserId = getAuthUserId as jest.MockedFunction<typeof getAuthUserId>;
const mockUpdateDeploymentTraffic = updateDeploymentTraffic as jest.MockedFunction<
  typeof updateDeploymentTraffic
>;
const mockGetDeployment = getDeployment as jest.MockedFunction<typeof getDeployment>;

function makeRequest(body: unknown): Request {
  return new Request("http://localhost/api/v1/deploy/dep-1/traffic", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

beforeEach(() => {
  jest.clearAllMocks();
});

describe("PATCH /api/v1/deploy/[id]/traffic", () => {
  it("returns 401 when there is no session", async () => {
    mockGetAuthUserId.mockResolvedValueOnce(null);
    const req = makeRequest({ split: 0.3 });
    const res = await PATCH(req, { params: Promise.resolve({ id: "dep-1" }) });
    expect(res.status).toBe(401);
  });

  it("returns 400 when split value is out of range", async () => {
    mockGetAuthUserId.mockResolvedValueOnce("user-1");
    mockGetDeployment.mockResolvedValueOnce({ id: "dep-1" } as never);
    const req = makeRequest({ split: 1.5 });
    const res = await PATCH(req, { params: Promise.resolve({ id: "dep-1" }) });
    expect(res.status).toBe(400);
  });

  it("returns 200 with ok:true on success", async () => {
    mockGetAuthUserId.mockResolvedValueOnce("user-1");
    mockGetDeployment.mockResolvedValueOnce({ id: "dep-1" } as never);
    mockUpdateDeploymentTraffic.mockResolvedValueOnce(undefined as never);

    const req = makeRequest({ split: 0.2 });
    const res = await PATCH(req, { params: Promise.resolve({ id: "dep-1" }) });
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body).toEqual({ ok: true });
    expect(mockUpdateDeploymentTraffic).toHaveBeenCalledWith("user-1", "dep-1", 0.2);
  });
});
