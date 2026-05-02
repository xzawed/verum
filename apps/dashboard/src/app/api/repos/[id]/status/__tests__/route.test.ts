jest.mock("@/lib/db/queries", () => ({
  getRepoStatus: jest.fn(),
  getWorkerAlive: jest.fn(),
}));
jest.mock("@/lib/api/handlers", () => ({
  getAuthUserId: jest.fn(),
}));

import { GET } from "../route";
import { getRepoStatus, getWorkerAlive } from "@/lib/db/queries";
import { getAuthUserId } from "@/lib/api/handlers";

const mockGetRepoStatus = getRepoStatus as jest.Mock;
const mockGetWorkerAlive = getWorkerAlive as jest.Mock;
const mockGetAuthUserId = getAuthUserId as jest.Mock;

function makeRequest(repoId: string): [Request, { params: Promise<{ id: string }> }] {
  const req = new Request(`http://localhost/api/repos/${repoId}/status`);
  const ctx = { params: Promise.resolve({ id: repoId }) };
  return [req, ctx];
}

beforeEach(() => {
  jest.clearAllMocks();
  mockGetAuthUserId.mockResolvedValue("user-1");
  mockGetWorkerAlive.mockResolvedValue(true);
});

describe("GET /api/repos/[id]/status", () => {
  it("returns 401 when session is missing", async () => {
    mockGetAuthUserId.mockResolvedValue(null);

    const [req, ctx] = makeRequest("repo-123");
    const res = await GET(req, ctx);

    expect(res.status).toBe(401);
  });

  it("returns 404 when repo status not found", async () => {
    mockGetRepoStatus.mockResolvedValue(null);

    const [req, ctx] = makeRequest("repo-ghost");
    const res = await GET(req, ctx);

    expect(res.status).toBe(404);
  });

  it("returns status and workerAlive on success", async () => {
    const fakeStatus = {
      repo_id: "repo-123",
      status: "analyze",
      latest_job_kind: "analyze",
      latest_job_status: "running",
    };
    mockGetRepoStatus.mockResolvedValue(fakeStatus);
    mockGetWorkerAlive.mockResolvedValue(true);

    const [req, ctx] = makeRequest("repo-123");
    const res = await GET(req, ctx);

    expect(res.status).toBe(200);
    const json = await res.json();
    expect(json.status).toEqual(fakeStatus);
    expect(json.workerAlive).toBe(true);
  });
});
