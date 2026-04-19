import { redirect } from "next/navigation";
import { signOut, auth } from "@/auth";
import { createRepo, deleteRepo } from "@/lib/db/jobs";
import { getRepos, getRepoStatus } from "@/lib/db/queries";

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

      <form
        action={async (formData: FormData) => {
          "use server";
          const session2 = await auth();
          if (!session2?.user) redirect("/login");
          const uid = String((session2.user as Record<string, unknown>).id ?? "");
          const repoUrl = formData.get("repo_url") as string;
          const branch = (formData.get("branch") as string) || "main";
          try {
            const repo = await createRepo(uid, repoUrl, branch);
            redirect(`/repos/${repo.id}`);
          } catch {
            redirect(`/repos?error=${encodeURIComponent("Failed to register repo")}`);
          }
        }}
        style={{ display: "flex", gap: 8, marginBottom: 32, padding: "16px", background: "#f9f9f9", border: "1px solid #eee" }}
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
        <button type="submit" style={{ padding: "8px 18px", fontWeight: "bold", fontSize: 13, cursor: "pointer" }}>
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
