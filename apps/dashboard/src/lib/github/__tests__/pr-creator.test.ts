import { GitHubPrCreator } from "../pr-creator";

const mockFetch = jest.fn();
global.fetch = mockFetch;

const BASE_SHA = "aabbcc112233";
const TREE_SHA = "ddeeff445566";
const NEW_BLOB_SHA = "111bbb";
const NEW_TREE_SHA = "222ccc";
const NEW_COMMIT_SHA = "333ddd";

function mockGitHubResponses() {
  mockFetch
    .mockResolvedValueOnce({ ok: true, json: async () => ({ object: { sha: BASE_SHA } }) })
    .mockResolvedValueOnce({ ok: true, json: async () => ({ tree: { sha: TREE_SHA } }) })
    .mockResolvedValueOnce({ ok: true, json: async () => ({ sha: NEW_BLOB_SHA }) })
    .mockResolvedValueOnce({ ok: true, json: async () => ({ sha: NEW_TREE_SHA }) })
    .mockResolvedValueOnce({ ok: true, json: async () => ({ sha: NEW_COMMIT_SHA }) })
    .mockResolvedValueOnce({ ok: true, json: async () => ({}) })
    .mockResolvedValueOnce({ ok: true, json: async () => ({ html_url: "https://github.com/owner/repo/pull/42", number: 42 }) });
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
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
      statusText: "Not Found",
      json: async () => ({}),
    });
    const creator = new GitHubPrCreator({ accessToken: "ghp_bad", repoFullName: "owner/repo" });
    await expect(
      creator.createPr({ branchName: "verum/x", baseBranch: "main", title: "t", body: "b", files: [] }),
    ).rejects.toThrow("GitHub API 404");
  });

  it("readFile returns null when file does not exist (404)", async () => {
    mockFetch.mockResolvedValueOnce({ ok: false, status: 404, statusText: "Not Found", json: async () => ({}) });
    const creator = new GitHubPrCreator({ accessToken: "ghp_test", repoFullName: "owner/repo" });
    const content = await creator.readFile(".env.example");
    expect(content).toBeNull();
  });

  it("readFile decodes base64 content", async () => {
    const encoded = Buffer.from("EXISTING_VAR=hello\n").toString("base64");
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ content: encoded + "\n", encoding: "base64" }),
    });
    const creator = new GitHubPrCreator({ accessToken: "ghp_test", repoFullName: "owner/repo" });
    const content = await creator.readFile(".env.example");
    expect(content).toBe("EXISTING_VAR=hello\n");
  });

  it("throws on invalid repoFullName", () => {
    expect(() => new GitHubPrCreator({ accessToken: "x", repoFullName: "invalid-no-slash" })).toThrow(
      "Invalid repoFullName",
    );
  });
});
