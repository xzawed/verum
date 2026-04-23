import { listUserRepos } from "../repos";

const mockRepo = {
  html_url: "https://github.com/user/repo",
  full_name: "user/repo",
  description: "A test repo",
  default_branch: "main",
  updated_at: "2026-04-01T00:00:00Z",
  private: false,
  fork: false,
  archived: false,
};

describe("listUserRepos", () => {
  let fetchSpy: jest.SpyInstance;

  beforeEach(() => {
    fetchSpy = jest.spyOn(global, "fetch");
  });

  afterEach(() => {
    fetchSpy.mockRestore();
  });

  it("returns array of repos on success", async () => {
    fetchSpy.mockResolvedValueOnce({
      ok: true,
      json: async () => [mockRepo],
    } as Response);

    const repos = await listUserRepos("test-token");
    expect(repos).toHaveLength(1);
    expect(repos[0]).toMatchObject({ full_name: "user/repo" });
  });

  it("throws on HTTP error (non-200 response)", async () => {
    fetchSpy.mockResolvedValueOnce({
      ok: false,
      status: 403,
      statusText: "Forbidden",
    } as Response);

    await expect(listUserRepos("bad-token")).rejects.toThrow("GitHub API error: 403 Forbidden");
  });

  it("passes Authorization header with Bearer token", async () => {
    fetchSpy.mockResolvedValueOnce({
      ok: true,
      json: async () => [],
    } as Response);

    await listUserRepos("my-access-token");

    expect(fetchSpy).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Bearer my-access-token",
        }),
      }),
    );
  });
});
