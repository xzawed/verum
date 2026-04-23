jest.mock("@/auth", () => ({ auth: jest.fn() }));
jest.mock("@/lib/db/jobs", () => ({
  approveGeneration: jest.fn(),
}));

import { PATCH } from "../route";
import { auth } from "@/auth";
import { approveGeneration } from "@/lib/db/jobs";

const mockAuth = auth as jest.MockedFunction<typeof auth>;
const mockApproveGeneration = approveGeneration as jest.MockedFunction<
  typeof approveGeneration
>;

function makeRequest(): Request {
  return new Request("http://localhost/api/v1/generate/gen-1/approve", {
    method: "PATCH",
  });
}

beforeEach(() => {
  jest.clearAllMocks();
});

describe("PATCH /api/v1/generate/[id]/approve", () => {
  it("returns 401 when there is no session", async () => {
    mockAuth.mockResolvedValueOnce(null);
    const req = makeRequest();
    const res = await PATCH(req, { params: Promise.resolve({ id: "gen-1" }) });
    expect(res.status).toBe(401);
  });

  it("returns 404 when generation is not found", async () => {
    mockAuth.mockResolvedValueOnce({ user: { id: "user-1" } } as never);
    mockApproveGeneration.mockResolvedValueOnce(false as never);

    const req = makeRequest();
    const res = await PATCH(req, { params: Promise.resolve({ id: "gen-missing" }) });
    expect(res.status).toBe(404);
  });

  it("returns 200 with status:approved on success", async () => {
    mockAuth.mockResolvedValueOnce({ user: { id: "user-1" } } as never);
    mockApproveGeneration.mockResolvedValueOnce(true as never);

    const req = makeRequest();
    const res = await PATCH(req, { params: Promise.resolve({ id: "gen-1" }) });
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body).toEqual({ status: "approved" });
    expect(mockApproveGeneration).toHaveBeenCalledWith("user-1", "gen-1");
  });
});
