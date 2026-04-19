import { redirect } from "next/navigation";
import { signOut } from "@/auth";
import { apiFetch, ApiError } from "@/lib/api";

interface RepoDetail {
  repo_id: string;
  github_url: string;
  default_branch: string;
  last_analyzed_at: string | null;
  created_at: string;
}

interface RepoStatus {
  repo: RepoDetail;
  latest_analysis: {
    analysis_id: string;
    status: string;
    call_sites_count: number | null;
    analyzed_at: string | null;
  } | null;
  latest_inference: {
    inference_id: string;
    status: string;
    domain: string | null;
    confidence: number | null;
    approved_sources: number;
    total_sources: number;
  } | null;
  latest_harvest: {
    inference_id: string;
    sources_done: number;
    sources_total: number;
    total_chunks: number;
  } | null;
}

async function fetchRepos(): Promise<RepoDetail[]> {
  try {
    return await apiFetch<RepoDetail[]>("/v1/me/repos");
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) redirect("/login");
    throw err;
  }
}

async function fetchRepoStatus(repoId: string): Promise<RepoStatus> {
  return apiFetch<RepoStatus>(`/v1/me/repos/${repoId}/status`);
}

export default async function ReposPage() {
  const repos = await fetchRepos();

  const statuses = await Promise.all(
    repos.map((r) =>
      fetchRepoStatus(r.repo_id).catch(() => null as RepoStatus | null)
    )
  );

  return (
    <main style={{ maxWidth: 840, margin: "40px auto", fontFamily: "monospace", padding: "0 16px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 32 }}>
        <h1 style={{ fontSize: 24, margin: 0 }}>Verum — My Repos</h1>
        <form
          action={async () => {
            "use server";
            await signOut({ redirectTo: "/login" });
          }}
        >
          <button
            type="submit"
            style={{ fontSize: 12, background: "none", border: "1px solid #ccc", cursor: "pointer", padding: "4px 10px" }}
          >
            Sign out
          </button>
        </form>
      </div>

      {/* Register form */}
      <form
        action={async (formData: FormData) => {
          "use server";
          const repoUrl = formData.get("repo_url") as string;
          const branch = (formData.get("branch") as string) || "main";
          try {
            const repo = await apiFetch<RepoDetail>("/v1/me/repos", {
              method: "POST",
              body: JSON.stringify({ repo_url: repoUrl, default_branch: branch }),
            });
            redirect(`/repos/${repo.repo_id}`);
          } catch (err) {
            if (err instanceof ApiError) {
              // Redirect back with error — simplified for MVP
              redirect(`/repos?error=${encodeURIComponent(err.message)}`);
            }
            throw err;
          }
        }}
        style={{
          display: "flex",
          gap: 8,
          marginBottom: 32,
          padding: "16px",
          background: "#f9f9f9",
          border: "1px solid #eee",
        }}
      >
        <input
          name="repo_url"
          type="url"
          placeholder="https://github.com/owner/repo"
          required
          style={{ flex: 1, padding: "8px 10px", fontSize: 13, border: "1px solid #ccc" }}
        />
        <input
          name="branch"
          type="text"
          placeholder="main"
          defaultValue="main"
          style={{ width: 80, padding: "8px 10px", fontSize: 13, border: "1px solid #ccc" }}
        />
        <button
          type="submit"
          style={{ padding: "8px 18px", fontWeight: "bold", fontSize: 13, cursor: "pointer" }}
        >
          + Register
        </button>
      </form>

      {repos.length === 0 && (
        <p style={{ color: "#888", textAlign: "center", marginTop: 60 }}>
          No repos registered yet. Add your first GitHub repo above.
        </p>
      )}

      {repos.map((repo, i) => {
        const status = statuses[i];
        return (
          <div
            key={repo.repo_id}
            style={{ border: "1px solid #ddd", padding: "16px 20px", marginBottom: 12 }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
              <div>
                <a
                  href={`/repos/${repo.repo_id}`}
                  style={{ fontWeight: "bold", fontSize: 15, color: "#0066cc", textDecoration: "none" }}
                >
                  {repo.github_url.replace("https://github.com/", "")}
                </a>
                <span style={{ marginLeft: 10, fontSize: 12, color: "#888" }}>
                  branch: {repo.default_branch}
                </span>
              </div>
              <form
                action={async () => {
                  "use server";
                  await apiFetch(`/v1/me/repos/${repo.repo_id}`, { method: "DELETE" });
                  redirect("/repos");
                }}
              >
                <button
                  type="submit"
                  style={{
                    fontSize: 11,
                    color: "#999",
                    background: "none",
                    border: "none",
                    cursor: "pointer",
                  }}
                >
                  delete
                </button>
              </form>
            </div>

            {/* Status chips */}
            <div style={{ display: "flex", gap: 12, marginTop: 10, flexWrap: "wrap" }}>
              <StatusChip
                label="ANALYZE"
                status={status?.latest_analysis?.status ?? null}
                detail={
                  status?.latest_analysis?.call_sites_count != null
                    ? `${status.latest_analysis.call_sites_count} call sites`
                    : undefined
                }
              />
              <StatusChip
                label="INFER"
                status={status?.latest_inference?.status ?? null}
                detail={status?.latest_inference?.domain ?? undefined}
              />
              <StatusChip
                label="HARVEST"
                status={
                  status?.latest_harvest
                    ? status.latest_harvest.sources_done >= status.latest_harvest.sources_total
                      ? "done"
                      : "running"
                    : null
                }
                detail={
                  status?.latest_harvest
                    ? `${status.latest_harvest.total_chunks.toLocaleString()} chunks`
                    : undefined
                }
              />
            </div>
          </div>
        );
      })}
    </main>
  );
}

function StatusChip({
  label,
  status,
  detail,
}: {
  label: string;
  status: string | null;
  detail?: string;
}) {
  const color =
    status === "done"
      ? "#22c55e"
      : status === "error"
        ? "#ef4444"
        : status === "running" || status === "pending"
          ? "#f59e0b"
          : "#ccc";

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12 }}>
      <span
        style={{
          display: "inline-block",
          width: 8,
          height: 8,
          borderRadius: "50%",
          background: color,
          flexShrink: 0,
        }}
      />
      <span style={{ fontWeight: "bold", color: "#444" }}>{label}</span>
      {status && (
        <span style={{ color: "#888" }}>
          {status}
          {detail ? ` · ${detail}` : ""}
        </span>
      )}
      {!status && <span style={{ color: "#ccc" }}>—</span>}
    </div>
  );
}
