import { redirect } from "next/navigation";
import { signOut, auth } from "@/auth";
import { createRepo, deleteRepo, enqueueAnalyze } from "@/lib/db/jobs";
import { getRepos, getRepoStatus, getLatestAnalysis } from "@/lib/db/queries";
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

  let repos: Awaited<ReturnType<typeof getRepos>> = [];
  let dbError: string | null = null;
  try {
    repos = await getRepos(userId);
  } catch {
    dbError = "Database unavailable — repository list cannot be loaded.";
  }

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
    <div className="p-6 max-w-3xl">
      {/* Page header */}
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Repositories</h1>
          <p className="mt-0.5 text-sm text-slate-500">Connect a repo to start the Verum Loop</p>
        </div>
        <form
          action={async () => {
            "use server";
            await signOut({ redirectTo: "/login" });
          }}
        >
          <button
            type="submit"
            className="rounded-md border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50 transition-colors"
          >
            Sign out
          </button>
        </form>
      </div>

      {/* Error banners */}
      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}
      {dbError && (
        <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
          {dbError}
        </div>
      )}

      {/* Registered repos */}
      {repos.length > 0 && (
        <section className="mb-8">
          <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-400">
            Connected ({repos.length})
          </p>
          <div className="flex flex-col gap-2">
            {repos.map((repo, i) => {
              const status = statuses[i];
              const name = repo.github_url.replace("https://github.com/", "");
              const analyze = status?.latestAnalysis;
              const infer = status?.latestInference;
              const isAnalyzing =
                analyze?.status === "pending" || analyze?.status === "running";
              const isInferring =
                infer?.status === "pending" || infer?.status === "running";

              return (
                <div
                  key={repo.id}
                  className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition-shadow hover:shadow-md"
                >
                  {/* Repo icon */}
                  <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-slate-100">
                    <GitHubIcon className="h-4 w-4 text-indigo-500" />
                  </div>

                  {/* Name + slug */}
                  <div className="min-w-0 flex-1">
                    <a
                      href={`/repos/${repo.id}`}
                      className="block truncate text-sm font-semibold text-slate-900 hover:text-indigo-600"
                    >
                      {name.split("/")[1] ?? name}
                    </a>
                    <p className="truncate font-mono text-xs text-slate-400">{name}</p>
                  </div>

                  {/* Stage pills */}
                  <div className="flex flex-shrink-0 items-center gap-1.5">
                    {analyze && (
                      <StagePill
                        label="ANALYZE"
                        status={analyze.status}
                        pulsing={isAnalyzing}
                        colorClass="bg-green-100 text-green-700"
                      />
                    )}
                    {infer && (
                      <StagePill
                        label="INFER"
                        status={infer.status}
                        pulsing={isInferring}
                        colorClass="bg-violet-100 text-violet-700"
                      />
                    )}
                    {status?.harvestChunks ? (
                      <StagePill
                        label="HARVEST"
                        status="done"
                        pulsing={false}
                        colorClass="bg-amber-100 text-amber-700"
                      />
                    ) : null}
                  </div>

                  {/* Chevron */}
                  <a href={`/repos/${repo.id}`} className="flex-shrink-0 text-slate-300 hover:text-slate-500">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <polyline points="9 18 15 12 9 6" />
                    </svg>
                  </a>

                  {/* Delete */}
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
                    <button
                      type="submit"
                      className="flex-shrink-0 text-xs text-slate-300 hover:text-red-500 transition-colors"
                      title="Remove repo"
                    >
                      ✕
                    </button>
                  </form>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* Empty state */}
      {repos.length === 0 && (
        <div className="mb-8 rounded-xl border border-dashed border-slate-300 py-12 text-center">
          <p className="text-sm text-slate-500">No repos connected yet.</p>
          <p className="mt-1 text-xs text-slate-400">Select a repository from the list below to get started.</p>
        </div>
      )}

      {/* GitHub repo picker */}
      <section>
        <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-400">
          Add from GitHub
        </p>

        {!token ? (
          <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
            <p className="mb-3 text-sm text-amber-800">
              Your session does not have GitHub repository access. Please sign out and sign back in.
            </p>
            <form
              action={async () => {
                "use server";
                await signOut({ redirectTo: "/login" });
              }}
            >
              <button type="submit" className="text-sm font-medium text-amber-700 underline">
                Sign out &amp; re-authorize
              </button>
            </form>
          </div>
        ) : githubError ? (
          <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            {githubError}
          </div>
        ) : githubRepos.length === 0 ? (
          <p className="text-sm text-slate-400">No public repositories found on your GitHub account.</p>
        ) : (
          <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
            {/* Search placeholder */}
            <div className="flex items-center gap-2 border-b border-slate-100 px-4 py-2.5">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="2">
                <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
              <span className="text-xs text-slate-400">Search repositories…</span>
            </div>

            <div className="max-h-80 overflow-y-auto divide-y divide-slate-50">
              {githubRepos.map((ghRepo) => {
                const alreadyRegistered = registeredUrls.has(ghRepo.html_url);
                return (
                  <div
                    key={ghRepo.html_url}
                    className={`flex items-center gap-3 px-4 py-3 ${alreadyRegistered ? "opacity-50" : "hover:bg-slate-50"}`}
                  >
                    <GitHubIcon className="h-4 w-4 flex-shrink-0 text-slate-400" />

                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <span className="font-mono text-sm font-medium text-slate-800 truncate">
                          {ghRepo.full_name}
                        </span>
                        {ghRepo.fork && (
                          <span className="rounded border border-slate-200 px-1 py-0.5 text-xs text-slate-400">fork</span>
                        )}
                        {ghRepo.archived && (
                          <span className="rounded border border-slate-200 px-1 py-0.5 text-xs text-slate-400">archived</span>
                        )}
                        {alreadyRegistered && (
                          <span className="rounded border border-green-200 px-1 py-0.5 text-xs text-green-600">registered</span>
                        )}
                      </div>
                      {ghRepo.description && (
                        <p className="mt-0.5 truncate text-xs text-slate-400">{ghRepo.description}</p>
                      )}
                    </div>

                    {!alreadyRegistered && (
                      <form
                        action={async () => {
                          "use server";
                          const s = await auth();
                          if (!s?.user) redirect("/login");
                          const uid = String((s.user as Record<string, unknown>).id ?? "");
                          const repo = await createRepo(uid, ghRepo.html_url, ghRepo.default_branch).catch(() => null);
                          if (!repo) redirect(`/repos?error=${encodeURIComponent("Failed to register repo")}`);
                          const latest = await getLatestAnalysis(repo.id);
                          if (!latest || (latest.status !== "pending" && latest.status !== "running")) {
                            await enqueueAnalyze({
                              userId: uid,
                              repoId: repo.id,
                              repoUrl: repo.github_url,
                              branch: repo.default_branch,
                            });
                          }
                          redirect(`/repos/${repo.id}`);
                        }}
                      >
                        <button
                          type="submit"
                          className="flex-shrink-0 rounded-md bg-indigo-500 px-3 py-1.5 text-xs font-semibold text-white hover:bg-indigo-600 transition-colors"
                        >
                          Connect
                        </button>
                      </form>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

function GitHubIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" className={className}>
      <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
    </svg>
  );
}

function StagePill({
  label,
  status,
  pulsing,
  colorClass,
}: {
  label: string;
  status: string;
  pulsing: boolean;
  colorClass: string;
}) {
  const isDone = status === "done";
  const isError = status === "error";
  return (
    <span
      className={`flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold ${
        isError ? "bg-red-100 text-red-700" : colorClass
      }`}
    >
      {pulsing ? (
        <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-current" />
      ) : isDone ? (
        "✓"
      ) : isError ? (
        "✗"
      ) : null}
      {label}
    </span>
  );
}
