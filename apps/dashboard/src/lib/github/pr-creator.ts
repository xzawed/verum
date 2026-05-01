export interface PrFile {
  path: string;
  content: string;
}

export interface CreatePrOptions {
  branchName: string;
  baseBranch: string;
  title: string;
  body: string;
  files: PrFile[];
}

export interface CreatePrResult {
  pr_url: string;
  pr_number: number;
  branch_name: string;
}

export class GitHubApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "GitHubApiError";
  }
}

export class GitHubPrCreator {
  private readonly token: string;
  private readonly owner: string;
  private readonly repo: string;
  private readonly base = process.env.GITHUB_API_BASE ?? "https://api.github.com";

  constructor(opts: { accessToken: string; repoFullName: string }) {
    this.token = opts.accessToken;
    const parts = opts.repoFullName.split("/");
    if (parts.length !== 2 || !parts[0] || !parts[1]) {
      throw new Error(`Invalid repoFullName: "${opts.repoFullName}" — expected "owner/repo"`);
    }
    this.owner = parts[0];
    this.repo = parts[1];
  }

  async createPr(opts: CreatePrOptions): Promise<CreatePrResult> {
    // Step 1: Get base branch HEAD SHA
    const refData = await this._request<{ object: { sha: string } }>(
      "GET",
      `/repos/${this.owner}/${this.repo}/git/ref/heads/${opts.baseBranch}`,
    );
    const baseSha = refData.object.sha;

    // Step 2: Get base commit's tree SHA
    const commitData = await this._request<{ tree: { sha: string } }>(
      "GET",
      `/repos/${this.owner}/${this.repo}/git/commits/${baseSha}`,
    );
    const baseTreeSha = commitData.tree.sha;

    // Step 3: Create a blob for each file
    const treeItems = await Promise.all(
      opts.files.map(async (file) => {
        const blob = await this._request<{ sha: string }>(
          "POST",
          `/repos/${this.owner}/${this.repo}/git/blobs`,
          { content: Buffer.from(file.content).toString("base64"), encoding: "base64" },
        );
        return { path: file.path, mode: "100644" as const, type: "blob" as const, sha: blob.sha };
      }),
    );

    // Step 4: Create new tree from base tree + modified blobs
    const newTree = await this._request<{ sha: string }>(
      "POST",
      `/repos/${this.owner}/${this.repo}/git/trees`,
      { base_tree: baseTreeSha, tree: treeItems },
    );

    // Step 5: Create commit pointing to new tree
    const newCommit = await this._request<{ sha: string }>(
      "POST",
      `/repos/${this.owner}/${this.repo}/git/commits`,
      { message: opts.title, tree: newTree.sha, parents: [baseSha] },
    );

    // Step 6: Create new branch pointing to the new commit
    await this._request(
      "POST",
      `/repos/${this.owner}/${this.repo}/git/refs`,
      { ref: `refs/heads/${opts.branchName}`, sha: newCommit.sha },
    );

    // Step 7: Open the PR
    const pr = await this._request<{ html_url: string; number: number }>(
      "POST",
      `/repos/${this.owner}/${this.repo}/pulls`,
      { title: opts.title, body: opts.body, head: opts.branchName, base: opts.baseBranch },
    );

    return { pr_url: pr.html_url, pr_number: pr.number, branch_name: opts.branchName };
  }

  async readFile(filePath: string): Promise<string | null> {
    try {
      const data = await this._request<{ content: string; encoding: string }>(
        "GET",
        `/repos/${this.owner}/${this.repo}/contents/${filePath}`,
      );
      if (data.encoding === "base64") {
        return Buffer.from(data.content.replace(/\n/g, ""), "base64").toString("utf-8");
      }
      return data.content;
    } catch (err) {
      if (err instanceof GitHubApiError && err.status === 404) {
        return null; // File genuinely does not exist
      }
      throw err; // Rate limit (403), auth error (401), server error (5xx) — caller must handle
    }
  }

  private async _request<T = unknown>(method: string, path: string, body?: unknown): Promise<T> {
    const url = `${this.base}${path}`;
    const res = await fetch(url, {
      method,
      headers: {
        Authorization: `Bearer ${this.token}`,
        Accept: "application/vnd.github+json",
        "Content-Type": "application/json",
        "X-GitHub-Api-Version": "2022-11-28",
      },
      ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
    });
    const text = await res.text();
    if (!res.ok) {
      throw new GitHubApiError(res.status, `GitHub API ${res.status}: ${method} ${path} — ${text}`);
    }
    try {
      return JSON.parse(text) as T;
    } catch {
      throw new GitHubApiError(res.status, `GitHub API response parse error: ${method} ${path} — ${text.slice(0, 200)}`);
    }
  }
}
