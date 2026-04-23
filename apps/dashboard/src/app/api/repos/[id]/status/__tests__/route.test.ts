jest.mock("@/lib/db/queries", () => ({
  getRepoStatus: jest.fn(),
  getWorkerAlive: jest.fn(),
}));
jest.mock("@/auth", () => ({
  auth: jest.fn(),
}));

import { GET } from "../route";
import { getRepoStatus, getWorkerAlive } from "@/lib/db/queries";
import { auth } from "@/auth";

const mockGetRepoStatus = getRepoStatus as jest.Mock;
const mockGetWorkerAlive = getWorkerAlive as jest.Mock;
const mockAuth = auth as jest.Mock;

function makeRequest(repoId: string): [Request, { params: Promise<{ id: string }> }] {
  const req = new Request(`http://localhost/api/repos/${repoId}/status`);
  const ctx = { params: Promise.resolve({ id: repoId }) };
  return [req, ctx];
}

beforeEach(() => {
  jest.clearAllMocks();
  mockAuth.mockResolvedValue({ user: { id: "user-1" } });
  mockGetWorkerAlive.mockResolvedValue(true);
});

describe("GET /api/repos/[id]/status", () => {
  it("returns 401 when session is missing", async () => {
    mockAuth.mockResolvedValue(null);

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
