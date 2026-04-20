export interface GithubRepoOption {
  html_url: string;
  full_name: string;
  description: string | null;
  default_branch: string;
  updated_at: string;
  private: boolean;
  fork: boolean;
  archived: boolean;
}

export async function listUserRepos(accessToken: string): Promise<GithubRepoOption[]> {
  const res = await fetch(
    "https://api.github.com/user/repos?per_page=100&sort=updated&affiliation=owner,collaborator",
    {
      headers: {
        Authorization: `Bearer ${accessToken}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
      },
      cache: "no-store",
    },
  );
  if (!res.ok) throw new Error(`GitHub API error: ${res.status} ${res.statusText}`);
  return (await res.json()) as GithubRepoOption[];
}
