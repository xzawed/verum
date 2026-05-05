jest.mock("@/lib/rateLimit", () => ({
  checkRateLimit: jest.fn().mockResolvedValue(null),
}));
jest.mock("@/lib/api/handlers", () => ({
  getAuthUserId: jest.fn(),
  createGetByIdHandler: jest.fn(),
}));
jest.mock("@/lib/db/queries", () => ({
  getGeneration: jest.fn(),
}));
jest.mock("@/lib/db/jobs", () => ({
  enqueueDeployment: jest.fn(),
}));

import { POST } from "../route";
import { getAuthUserId } from "@/lib/api/handlers";
import { getGeneration } from "@/lib/db/queries";
import { enqueueDeployment } from "@/lib/db/jobs";

const mockGetAuthUserId = getAuthUserId as jest.MockedFunction<typeof getAuthUserId>;
const mockGetGeneration = getGeneration as jest.MockedFunction<typeof getGeneration>;
const mockEnqueueDeployment = enqueueDeployment as jest.MockedFunction<typeof enqueueDeployment>;

function makeRequest(body: unknown): Request {
  return new Request("http://localhost/api/v1/deploy", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

beforeEach(() => {
  jest.clearAllMocks();
});

describe("POST /api/v1/deploy", () => {
  it("returns 401 when not authenticated", async () => {
    mockGetAuthUserId.mockResolvedValue(null);

    const res = await POST(makeRequest({ generation_id: "aaaaaaaa-0000-4000-8000-000000000004" }));

    expect(res.status).toBe(401);
  });

  it("returns 400 when generation_id is missing", async () => {
    mockGetAuthUserId.mockResolvedValue("user-1");

    const res = await POST(makeRequest({}));

    expect(res.status).toBe(400);
  });

  it("returns 404 when generation is not found", async () => {
    mockGetAuthUserId.mockResolvedValue("user-1");
    mockGetGeneration.mockResolvedValue(null);

    const res = await POST(makeRequest({ generation_id: "aaaaaaaa-0000-4000-8000-000000000099" }));

    expect(res.status).toBe(404);
  });

  it("returns 409 when generation status is not approved", async () => {
    mockGetAuthUserId.mockResolvedValue("user-1");
    mockGetGeneration.mockResolvedValue({ id: "gen-1", status: "pending" } as any);

    const res = await POST(makeRequest({ generation_id: "aaaaaaaa-0000-4000-8000-000000000004" }));

    expect(res.status).toBe(409);
  });

  it("returns 202 with job_id on success", async () => {
    mockGetAuthUserId.mockResolvedValue("user-1");
    mockGetGeneration.mockResolvedValue({ id: "gen-1", status: "approved" } as any);
    mockEnqueueDeployment.mockResolvedValue("deploy-job-1");

    const res = await POST(makeRequest({ generation_id: "aaaaaaaa-0000-4000-8000-000000000004" }));

    expect(res.status).toBe(202);
    const json = await res.json();
    expect(json).toEqual({ job_id: "deploy-job-1" });
  });
});
