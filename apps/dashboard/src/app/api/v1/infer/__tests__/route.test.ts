jest.mock("@/lib/rateLimit", () => ({
  checkRateLimit: jest.fn().mockResolvedValue(null),
}));
jest.mock("@/lib/api/handlers", () => ({
  getAuthUserId: jest.fn(),
  createGetByIdHandler: jest.fn(),
}));
jest.mock("@/lib/db/queries", () => ({
  getAnalysis: jest.fn(),
}));
jest.mock("@/lib/db/jobs", () => ({
  enqueueInfer: jest.fn(),
}));

import { POST } from "../route";
import { getAuthUserId } from "@/lib/api/handlers";
import { getAnalysis } from "@/lib/db/queries";
import { enqueueInfer } from "@/lib/db/jobs";

const mockGetAuthUserId = getAuthUserId as jest.MockedFunction<typeof getAuthUserId>;
const mockGetAnalysis = getAnalysis as jest.MockedFunction<typeof getAnalysis>;
const mockEnqueueInfer = enqueueInfer as jest.MockedFunction<typeof enqueueInfer>;

function makeRequest(body: unknown): Request {
  return new Request("http://localhost/api/v1/infer", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

beforeEach(() => {
  jest.clearAllMocks();
});

describe("POST /api/v1/infer", () => {
  it("returns 401 when not authenticated", async () => {
    mockGetAuthUserId.mockResolvedValue(null);

    const res = await POST(makeRequest({ analysis_id: "aaaaaaaa-0000-0000-0000-000000000001", repo_id: "aaaaaaaa-0000-0000-0000-000000000002" }));

    expect(res.status).toBe(401);
  });

  it("returns 400 when analysis_id or repo_id is missing", async () => {
    mockGetAuthUserId.mockResolvedValue("user-1");

    const res = await POST(makeRequest({ repo_id: "aaaaaaaa-0000-0000-0000-000000000002" }));

    expect(res.status).toBe(400);
  });

  it("returns 404 when analysis is not found", async () => {
    mockGetAuthUserId.mockResolvedValue("user-1");
    mockGetAnalysis.mockResolvedValue(null);

    const res = await POST(makeRequest({ analysis_id: "aaaaaaaa-0000-0000-0000-000000000099", repo_id: "aaaaaaaa-0000-0000-0000-000000000002" }));

    expect(res.status).toBe(404);
  });

  it("returns 202 with job_id on success", async () => {
    mockGetAuthUserId.mockResolvedValue("user-1");
    mockGetAnalysis.mockResolvedValue({ id: "a-1", repo_id: "r-1", status: "done" } as any);
    mockEnqueueInfer.mockResolvedValue({ id: "inf-job-1" } as any);

    const res = await POST(makeRequest({ analysis_id: "aaaaaaaa-0000-0000-0000-000000000001", repo_id: "aaaaaaaa-0000-0000-0000-000000000002" }));

    expect(res.status).toBe(202);
    const json = await res.json();
    expect(json).toEqual({ job_id: "inf-job-1" });
  });
});
