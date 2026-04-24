jest.mock("@/lib/api/handlers", () => ({
  getAuthUserId: jest.fn(),
  createGetByIdHandler: jest.fn(),
}));
jest.mock("@/lib/db/queries", () => ({
  getRepo: jest.fn(),
}));
jest.mock("@/lib/db/jobs", () => ({
  enqueueAnalyze: jest.fn(),
}));

import { POST } from "../route";
import { getAuthUserId } from "@/lib/api/handlers";
import { getRepo } from "@/lib/db/queries";
import { enqueueAnalyze } from "@/lib/db/jobs";

const mockGetAuthUserId = getAuthUserId as jest.MockedFunction<typeof getAuthUserId>;
const mockGetRepo = getRepo as jest.MockedFunction<typeof getRepo>;
const mockEnqueueAnalyze = enqueueAnalyze as jest.MockedFunction<typeof enqueueAnalyze>;

function makeRequest(body: unknown): Request {
  return new Request("http://localhost/api/v1/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

beforeEach(() => {
  jest.clearAllMocks();
});

describe("POST /api/v1/analyze", () => {
  it("returns 401 when not authenticated", async () => {
    mockGetAuthUserId.mockResolvedValue(null);

    const res = await POST(makeRequest({ repo_id: "aaaaaaaa-0000-0000-0000-000000000002" }));

    expect(res.status).toBe(401);
  });

  it("returns 400 when repo_id is missing", async () => {
    mockGetAuthUserId.mockResolvedValue("user-1");

    const res = await POST(makeRequest({}));

    expect(res.status).toBe(400);
  });

  it("returns 404 when repo is not found", async () => {
    mockGetAuthUserId.mockResolvedValue("user-1");
    mockGetRepo.mockResolvedValue(null);

    const res = await POST(makeRequest({ repo_id: "aaaaaaaa-0000-0000-0000-000000000099" }));

    expect(res.status).toBe(404);
  });

  it("returns 202 with job_id on success", async () => {
    mockGetAuthUserId.mockResolvedValue("user-1");
    mockGetRepo.mockResolvedValue({
      id: "repo-1",
      github_url: "https://github.com/owner/repo",
      default_branch: "main",
    } as any);
    mockEnqueueAnalyze.mockResolvedValue({ id: "job-abc" } as any);

    const res = await POST(makeRequest({ repo_id: "aaaaaaaa-0000-0000-0000-000000000002" }));

    expect(res.status).toBe(202);
    const json = await res.json();
    expect(json).toEqual({ job_id: "job-abc" });
  });
});
