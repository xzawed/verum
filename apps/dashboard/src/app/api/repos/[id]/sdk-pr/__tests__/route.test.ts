import { POST, GET } from "../route";
import { NextRequest } from "next/server";

jest.mock("@/auth", () => ({
  auth: jest.fn().mockResolvedValue({
    user: { id: "user-1", github_access_token: "ghp_test_token" },
  }),
}));

jest.mock("@/lib/api/handlers", () => ({
  getAuthUserId: jest.fn().mockResolvedValue("user-1"),
}));

jest.mock("@/lib/db/queries", () => ({
  getRepo: jest.fn().mockResolvedValue({
    id: "repo-1",
    github_url: "https://github.com/owner/testrepo",
    default_branch: "main",
    owner_user_id: "user-1",
  }),
  getLatestAnalysis: jest.fn().mockResolvedValue({
    id: "analysis-1",
    status: "done",
    call_sites: [
      { file_path: "src/ai.ts", line: 10, sdk: "openai", function: "chat.completions.create", prompt_ref: null },
    ],
  }),
  getLatestSdkPrRequest: jest.fn().mockResolvedValue(null),
}));

jest.mock("@/lib/db/jobs", () => ({
  createSdkPrRequest: jest.fn().mockResolvedValue("sdk-req-1"),
  updateSdkPrRequest: jest.fn().mockResolvedValue(undefined),
}));

jest.mock("@/lib/github/pr-creator", () => ({
  GitHubPrCreator: jest.fn().mockImplementation(() => ({
    readFile: jest.fn().mockResolvedValue(null),
    createPr: jest.fn().mockResolvedValue({
      pr_url: "https://github.com/owner/testrepo/pull/7",
      pr_number: 7,
      branch_name: "verum/sdk-integration-12345",
    }),
  })),
}));

jest.mock("@/lib/rateLimit", () => ({
  checkRateLimit: jest.fn().mockResolvedValue(null),
}));

jest.mock("@/lib/sdk-pr/transformer", () => ({
  buildPrFileChanges: jest.fn().mockReturnValue([
    { path: "src/lib/verum/client.ts", content: "export class VerumClient {}" },
    { path: ".env.example", content: "VERUM_API_URL=\n" },
    { path: "src/ai.ts", content: "// TODO: [Verum]\nconst res = await openai.create();\n" },
  ]),
}));

const makeRequest = (method = "POST") =>
  new NextRequest("http://localhost/api/repos/repo-1/sdk-pr", { method });
const makeParams = () => Promise.resolve({ id: "repo-1" });

describe("POST /api/repos/[id]/sdk-pr", () => {
  it("returns 201 with pr_url and files_changed on success", async () => {
    const res = await POST(makeRequest(), { params: makeParams() });
    expect(res.status).toBe(201);
    const body = await res.json() as Record<string, unknown>;
    expect(body.pr_url).toBe("https://github.com/owner/testrepo/pull/7");
    expect(body.pr_number).toBe(7);
    expect(body.files_changed).toBe(3);
    expect(body.request_id).toBe("sdk-req-1");
  });

  it("returns 401 when not authenticated", async () => {
    const { auth } = await import("@/auth");
    (auth as jest.Mock).mockResolvedValueOnce(null);
    const res = await POST(makeRequest(), { params: makeParams() });
    expect(res.status).toBe(401);
  });

  it("returns 401 when github_access_token is missing", async () => {
    const { auth } = await import("@/auth");
    (auth as jest.Mock).mockResolvedValueOnce({ user: { id: "user-1" } });
    const res = await POST(makeRequest(), { params: makeParams() });
    expect(res.status).toBe(401);
  });

  it("returns 404 when repo not found", async () => {
    const { getRepo } = await import("@/lib/db/queries");
    (getRepo as jest.Mock).mockResolvedValueOnce(null);
    const res = await POST(makeRequest(), { params: makeParams() });
    expect(res.status).toBe(404);
  });

  it("returns 409 when analysis is not done", async () => {
    const { getLatestAnalysis } = await import("@/lib/db/queries");
    (getLatestAnalysis as jest.Mock).mockResolvedValueOnce({ id: "a-1", status: "running", call_sites: [] });
    const res = await POST(makeRequest(), { params: makeParams() });
    expect(res.status).toBe(409);
  });
});

describe("GET /api/repos/[id]/sdk-pr", () => {
  it("returns 404 when no SDK PR request exists", async () => {
    const { getLatestSdkPrRequest } = await import("@/lib/db/queries");
    (getLatestSdkPrRequest as jest.Mock).mockResolvedValueOnce(null);
    const res = await GET(makeRequest("GET"), { params: makeParams() });
    expect(res.status).toBe(404);
  });

  it("returns 200 with the latest request when it exists", async () => {
    const { getLatestSdkPrRequest } = await import("@/lib/db/queries");
    (getLatestSdkPrRequest as jest.Mock).mockResolvedValueOnce({
      id: "req-1", status: "pr_created", pr_url: "https://github.com/o/r/pull/7", pr_number: 7,
    });
    const res = await GET(makeRequest("GET"), { params: makeParams() });
    expect(res.status).toBe(200);
    const body = await res.json() as Record<string, unknown>;
    expect(body.pr_url).toBe("https://github.com/o/r/pull/7");
  });
});
