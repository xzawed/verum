import { redirect } from "next/navigation";
import { signOut, auth } from "@/auth";
import { createRepo, deleteRepo } from "@/lib/db/jobs";
import { getRepos, getRepoStatus } from "@/lib/db/queries";
import { listUserRepos } from "@/lib/github/repos";

export default async function ReposPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string }>;
}) {
  const session = await auth();
  if (!session?.user) redirect("/login");

  const u = session.user as Record<string, unknown>;
  const userId = String(u.id ?? "");
  if (!userId) redirect("/login");

  const { error } = await searchParams;
  const repos = await getRepos(userId);

  const statuses = await Promise.all(
    repos.map((r) => getRepoStatus(userId, r.id).catch(() => null)),
  );

  const registeredUrls = new Set(repos.map((r) => r.github_url));

  const token = (u.github_access_token ?? undefined) as string | undefined;

  let githubRepos: Awaited<ReturnType<typeof listUserRepos>> = [];
  let githubError: string | null = null;

  if (token) {
    try {
      githubRepos = await listUserRepos(token);
    } catch (e) {
      githubError = e instanceof Error ? e.message : "Failed to load GitHub repositories";
    }
  }

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

      {error && (
        <p style={{ color: "red", marginBottom: 16, fontSize: 13 }}>Error: {error}</p>
      )}

      {/* GitHub repo picker */}
      <div style={{ marginBottom: 32 }}>
        <h2 style={{ fontSize: 14, fontWeight: "bold", marginBottom: 10, color: "#444" }}>
          Add a Repository
        </h2>

        {!token ? (
          <div style={{ padding: "16px", background: "#fff8e1", border: "1px solid #ffe082", fontSize: 13 }}>
            <p style={{ margin: "0 0 10px" }}>
              Your session does not have GitHub repository access. Please sign out and sign back in to grant access.
            </p>
            <form
              action={async () => {
                "use server";
                await signOut({ redirectTo: "/login" });
              }}
            >
              <button type="submit" style={{ fontSize: 12, cursor: "pointer", padding: "4px 12px" }}>
                Sign out &amp; re-authorize
              </button>
            </form>
          </div>
        ) : githubError ? (
          <div style={{ padding: "12px", background: "#fdecea", border: "1px solid #f5c6c6", fontSize: 13 }}>
            {githubError}
          </div>
        ) : githubRepos.length === 0 ? (
          <p style={{ color: "#888", fontSize: 13 }}>No public repositories found on your GitHub account.</p>
        ) : (
          <div style={{ border: "1px solid #ddd", background: "#fafafa", maxHeight: 360, overflowY: "auto" }}>
            {githubRepos.map((ghRepo) => {
              const alreadyRegistered = registeredUrls.has(ghRepo.html_url);
              return (
                <div
                  key={ghRepo.html_url}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    padding: "10px 16px",
                    borderBottom: "1px solid #eee",
                    opacity: alreadyRegistered ? 0.5 : 1,
                  }}
                >
                  <div style={{ flex: 1, minWidth: 0, marginRight: 12 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                      <span style={{ fontWeight: "bold", fontSize: 13 }}>
                        {ghRepo.full_name}
                      </span>
                      {ghRepo.fork && (
                        <span style={{ fontSize: 10, color: "#888", border: "1px solid #ccc", padding: "1px 5px" }}>fork</span>
                      )}
                      {ghRepo.archived && (
                        <span style={{ fontSize: 10, color: "#888", border: "1px solid #ccc", padding: "1px 5px" }}>archived</span>
                      )}
                      {alreadyRegistered && (
                        <span style={{ fontSize: 10, color: "#22c55e", border: "1px solid #22c55e", padding: "1px 5px" }}>registered</span>
                      )}
                    </div>
                    {ghRepo.description && (
                      <p style={{ margin: "3px 0 0", fontSize: 11, color: "#888", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {ghRepo.description}
                      </p>
                    )}
                    <p style={{ margin: "2px 0 0", fontSize: 10, color: "#aaa" }}>
                      branch: {ghRepo.default_branch} · updated {new Date(ghRepo.updated_at).toLocaleDateString()}
                    </p>
                  </div>

                  {!alreadyRegistered && (
                    <form
                      action={async () => {
                        "use server";
                        const s = await auth();
                        if (!s?.user) redirect("/login");
                        const uid = String((s.user as Record<string, unknown>).id ?? "");
                        try {
                          const repo = await createRepo(uid, ghRepo.html_url, ghRepo.default_branch);
                          redirect(`/repos/${repo.id}`);
                        } catch {
                          redirect(`/repos?error=${encodeURIComponent("Failed to register repo")}`);
                        }
                      }}
                    >
                      <button
                        type="submit"
                        style={{ fontSize: 12, padding: "4px 12px", cursor: "pointer", whiteSpace: "nowrap" }}
                      >
                        + Register
                      </button>
                    </form>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Registered repos list */}
      {repos.length === 0 ? (
        <p style={{ color: "#888", textAlign: "center", marginTop: 60 }}>
          No repos registered yet. Select a repo above.
        </p>
      ) : (
        <>
          <h2 style={{ fontSize: 14, fontWeight: "bold", marginBottom: 10, color: "#444" }}>
            Registered Repos
          </h2>
          {repos.map((repo, i) => {
            const status = statuses[i];
            return (
              <div key={repo.id} style={{ border: "1px solid #ddd", padding: "16px 20px", marginBottom: 12 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <div>
                    <a
                      href={`/repos/${repo.id}`}
                      style={{ fontWeight: "bold", fontSize: 15, color: "#0066cc", textDecoration: "none" }}
                    >
                      {repo.github_url.replace("https://github.com/", "")}
                    </a>
                    <span style={{ marginLeft: 10, fontSize: 12, color: "#888" }}>branch: {repo.default_branch}</span>
                  </div>
                  <form
                    action={async () => {
                      "use server";
                      const s = await auth();
                      if (!s?.user) return;
                      const uid = String((s.user as Record<string, unknown>).id ?? "");
                      await deleteRepo(uid, repo.id);
                      redirect("/repos");
                    }}
                  >
                    <button type="submit" style={{ fontSize: 11, color: "#999", background: "none", border: "none", cursor: "pointer" }}>
                      delete
                    </button>
                  </form>
                </div>

                <div style={{ display: "flex", gap: 12, marginTop: 10, flexWrap: "wrap" }}>
                  <StatusChip
                    label="ANALYZE"
                    status={status?.latestAnalysis?.status ?? null}
                    detail={
                      status?.latestAnalysis?.call_sites != null
                        ? `${(status.latestAnalysis.call_sites as unknown[]).length} call sites`
                        : undefined
                    }
                  />
                  <StatusChip
                    label="INFER"
                    status={status?.latestInference?.status ?? null}
                    detail={status?.latestInference?.domain ?? undefined}
                  />
                  <StatusChip
                    label="HARVEST"
                    status={
                      status?.harvestChunks
                        ? status.harvestSourcesDone >= status.harvestSourcesTotal && status.harvestSourcesTotal > 0
                          ? "done"
                          : "running"
                        : null
                    }
                    detail={status?.harvestChunks ? `${status.harvestChunks.toLocaleString()} chunks` : undefined}
                  />
                </div>
              </div>
            );
          })}
        </>
      )}
    </main>
  );
}

function StatusChip({ label, status, detail }: { label: string; status: string | null; detail?: string }) {
  const color =
    status === "done" ? "#22c55e" :
    status === "error" ? "#ef4444" :
    status === "running" || status === "pending" ? "#f59e0b" : "#ccc";

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12 }}>
      <span style={{ display: "inline-block", width: 8, height: 8, borderRadius: "50%", background: color, flexShrink: 0 }} />
      <span style={{ fontWeight: "bold", color: "#444" }}>{label}</span>
      {status ? <span style={{ color: "#888" }}>{status}{detail ? ` · ${detail}` : ""}</span> : <span style={{ color: "#ccc" }}>—</span>}
    </div>
  );
}
