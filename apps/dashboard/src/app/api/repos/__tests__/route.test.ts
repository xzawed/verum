jest.mock("@/lib/api/handlers", () => ({ getAuthUserId: jest.fn() }));
jest.mock("@/lib/rateLimit", () => ({
  checkRateLimitDual: jest.fn(),
  getClientIp: jest.fn().mockReturnValue("127.0.0.1"),
}));
jest.mock("@/lib/db/jobs", () => ({ createRepo: jest.fn() }));
jest.mock("@/lib/db/queries", () => ({ getRepos: jest.fn() }));

import { GET, POST } from "../route";
import { getAuthUserId } from "@/lib/api/handlers";
import { checkRateLimitDual } from "@/lib/rateLimit";
import { createRepo } from "@/lib/db/jobs";
import { getRepos } from "@/lib/db/queries";

const mockGetAuthUserId = getAuthUserId as jest.Mock;
const mockCheckRateLimitDual = checkRateLimitDual as jest.Mock;
const mockCreateRepo = createRepo as jest.Mock;
const mockGetRepos = getRepos as jest.Mock;

function makePostRequest(body: unknown): Request {
  return new Request("http://localhost/api/repos", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

beforeEach(() => {
  jest.clearAllMocks();
  mockGetAuthUserId.mockResolvedValue("user-1");
  mockCheckRateLimitDual.mockResolvedValue(null); // no rate-limit hit
});

describe("GET /api/repos", () => {
  it("returns 401 when unauthenticated", async () => {
    mockGetAuthUserId.mockResolvedValue(null);
    const res = await GET();
    expect(res.status).toBe(401);
  });

  it("returns repos for authenticated user", async () => {
    const repos = [{ id: "r1", repo_url: "https://github.com/a/b" }];
    mockGetRepos.mockResolvedValue(repos);
    const res = await GET();
    expect(res.status).toBe(200);
    const json = await res.json();
    expect(json).toEqual(repos);
  });
});

describe("POST /api/repos", () => {
  it("returns 401 when unauthenticated", async () => {
    mockGetAuthUserId.mockResolvedValue(null);
    const res = await POST(makePostRequest({ repo_url: "https://github.com/a/b" }));
    expect(res.status).toBe(401);
  });

  it("returns rate-limit response when rate limit hit", async () => {
    mockCheckRateLimitDual.mockResolvedValue(new Response("rate limited", { status: 429 }));
    const res = await POST(makePostRequest({ repo_url: "https://github.com/a/b" }));
    expect(res.status).toBe(429);
  });

  it("returns 400 for invalid body", async () => {
    const res = await POST(makePostRequest({ repo_url: "not-a-url" }));
    expect(res.status).toBe(400);
  });

  it("returns 400 for non-github URL in production mode", async () => {
    const saved = process.env.VERUM_TEST_MODE;
    delete process.env.VERUM_TEST_MODE;
    // Must re-import module to pick up new env — test with a fresh isolated module
    jest.resetModules();
    jest.mock("@/lib/api/handlers", () => ({ getAuthUserId: jest.fn().mockResolvedValue("user-1") }));
    jest.mock("@/lib/rateLimit", () => ({
      checkRateLimitDual: jest.fn().mockResolvedValue(null),
      getClientIp: jest.fn().mockReturnValue("127.0.0.1"),
    }));
    jest.mock("@/lib/db/jobs", () => ({ createRepo: jest.fn() }));
    jest.mock("@/lib/db/queries", () => ({ getRepos: jest.fn() }));
    const { POST: POST2 } = await import("../route");
    const res = await POST2(makePostRequest({ repo_url: "http://internal-host/repo" }));
    expect(res.status).toBe(400);
    process.env.VERUM_TEST_MODE = saved ?? "";
  });

  it("accepts non-github URL when VERUM_TEST_MODE=1", async () => {
    process.env.VERUM_TEST_MODE = "1";
    jest.resetModules();
    jest.mock("@/lib/api/handlers", () => ({ getAuthUserId: jest.fn().mockResolvedValue("user-1") }));
    jest.mock("@/lib/rateLimit", () => ({
      checkRateLimitDual: jest.fn().mockResolvedValue(null),
      getClientIp: jest.fn().mockReturnValue("127.0.0.1"),
    }));
    jest.mock("@/lib/db/jobs", () => ({
      createRepo: jest.fn().mockResolvedValue({ id: "r1" }),
    }));
    jest.mock("@/lib/db/queries", () => ({ getRepos: jest.fn() }));
    const { POST: POST3 } = await import("../route");
    const res = await POST3(makePostRequest({ repo_url: "http://git-http/org/repo" }));
    expect(res.status).toBe(201);
    delete process.env.VERUM_TEST_MODE;
  });

  it("creates repo and returns 201 for valid github URL", async () => {
    mockCreateRepo.mockResolvedValue({ id: "r1", repo_url: "https://github.com/a/b" });
    const res = await POST(makePostRequest({ repo_url: "https://github.com/a/b" }));
    expect(res.status).toBe(201);
    const json = await res.json();
    expect(json.id).toBe("r1");
  });

  it("passes optional branch to createRepo", async () => {
    mockCreateRepo.mockResolvedValue({ id: "r2" });
    const res = await POST(makePostRequest({ repo_url: "https://github.com/a/b", branch: "dev" }));
    expect(res.status).toBe(201);
    expect(mockCreateRepo).toHaveBeenCalledWith("user-1", "https://github.com/a/b", "dev");
  });
});
