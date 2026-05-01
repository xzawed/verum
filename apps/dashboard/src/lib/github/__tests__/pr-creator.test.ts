import { GitHubPrCreator } from "../pr-creator";

const mockFetch = jest.fn();
global.fetch = mockFetch;

const BASE_SHA = "aabbcc112233";
const TREE_SHA = "ddeeff445566";
const NEW_BLOB_SHA = "111bbb";
const NEW_TREE_SHA = "222ccc";
const NEW_COMMIT_SHA = "333ddd";

function ok(data: unknown) {
  return { ok: true, status: 200, text: async () => JSON.stringify(data) };
}

function err(status: number, body: string) {
  return { ok: false, status, text: async () => body };
}

function mockGitHubResponses() {
  mockFetch
    .mockResolvedValueOnce(ok({ object: { sha: BASE_SHA } }))
    .mockResolvedValueOnce(ok({ tree: { sha: TREE_SHA } }))
    .mockResolvedValueOnce(ok({ sha: NEW_BLOB_SHA }))
    .mockResolvedValueOnce(ok({ sha: NEW_TREE_SHA }))
    .mockResolvedValueOnce(ok({ sha: NEW_COMMIT_SHA }))
    .mockResolvedValueOnce(ok({}))
    .mockResolvedValueOnce(ok({ html_url: "https://github.com/owner/repo/pull/42", number: 42 }));
}

describe("GitHubPrCreator", () => {
  beforeEach(() => mockFetch.mockReset());

  it("creates PR and returns pr_url + pr_number", async () => {
    mockGitHubResponses();
    const creator = new GitHubPrCreator({ accessToken: "ghp_test123", repoFullName: "owner/repo" });
    const result = await creator.createPr({
      branchName: "verum/sdk-integration",
      baseBranch: "main",
      title: "Add Verum SDK",
      body: "PR body",
      files: [{ path: "src/lib/verum/client.ts", content: "export class VerumClient {}" }],
    });
    expect(result.pr_url).toBe("https://github.com/owner/repo/pull/42");
    expect(result.pr_number).toBe(42);
    expect(result.branch_name).toBe("verum/sdk-integration");
    expect(mockFetch).toHaveBeenCalledTimes(7);
  });

  it("throws a descriptive error on 404 from GitHub", async () => {
    mockFetch.mockResolvedValueOnce(err(404, '{"message":"Not Found"}'));
    const creator = new GitHubPrCreator({ accessToken: "ghp_bad", repoFullName: "owner/repo" });
    await expect(
      creator.createPr({ branchName: "verum/x", baseBranch: "main", title: "t", body: "b", files: [] }),
    ).rejects.toThrow("GitHub API 404");
  });

  it("error message includes GitHub response body, not just statusText", async () => {
    mockFetch.mockResolvedValueOnce(err(422, '{"message":"tree must not be empty","documentation_url":"https://docs.github.com"}'));
    const creator = new GitHubPrCreator({ accessToken: "ghp_test", repoFullName: "owner/repo" });
    await expect(creator.readFile("file.txt")).rejects.toThrow("tree must not be empty");
  });

  it("throws GitHubApiError with parse error when response is not JSON", async () => {
    // Simulate GitHub returning HTML (e.g. during an incident) — text() returns raw HTML, not JSON
    mockFetch.mockResolvedValueOnce({ ok: true, status: 200, text: async () => "<html>GitHub is down</html>" });
    const creator = new GitHubPrCreator({ accessToken: "ghp_test", repoFullName: "owner/repo" });
    await expect(creator.readFile("file.txt")).rejects.toThrow("GitHub API response parse error");
  });

  it("readFile returns null when file does not exist (404)", async () => {
    mockFetch.mockResolvedValueOnce(err(404, '{"message":"Not Found"}'));
    const creator = new GitHubPrCreator({ accessToken: "ghp_test", repoFullName: "owner/repo" });
    const content = await creator.readFile(".env.example");
    expect(content).toBeNull();
  });

  it("readFile decodes base64 content", async () => {
    const encoded = Buffer.from("EXISTING_VAR=hello\n").toString("base64");
    mockFetch.mockResolvedValueOnce(ok({ content: encoded + "\n", encoding: "base64" }));
    const creator = new GitHubPrCreator({ accessToken: "ghp_test", repoFullName: "owner/repo" });
    const content = await creator.readFile(".env.example");
    expect(content).toBe("EXISTING_VAR=hello\n");
  });

  it("throws on invalid repoFullName", () => {
    expect(() => new GitHubPrCreator({ accessToken: "x", repoFullName: "invalid-no-slash" })).toThrow(
      "Invalid repoFullName",
    );
  });

  it("readFile re-throws non-404 GitHub errors", async () => {
    mockFetch.mockResolvedValueOnce(err(403, '{"message":"Forbidden"}'));
    const creator = new GitHubPrCreator({ accessToken: "ghp_test", repoFullName: "owner/repo" });
    await expect(creator.readFile("secrets.txt")).rejects.toThrow("GitHub API 403");
  });

  it("readFile returns raw content when not base64-encoded", async () => {
    mockFetch.mockResolvedValueOnce(ok({ content: "plain text content", encoding: "utf-8" }));
    const creator = new GitHubPrCreator({ accessToken: "ghp_test", repoFullName: "owner/repo" });
    const content = await creator.readFile("README.md");
    expect(content).toBe("plain text content");
  });
});
