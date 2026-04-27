# Dashboard UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the Verum dashboard from a plain monospace-only layout into a clean light SaaS UI with icon sidebar, design token system, and polished pages.

**Architecture:** Add a root `layout.tsx` + `AppShell` client component that conditionally renders a 56px icon sidebar for all routes except `/login`. Each page's inline styles are replaced with Tailwind v4 utility classes using the Slate/Indigo color tokens agreed in the spec.

**Tech Stack:** Next.js 16 App Router, React 19, Tailwind CSS v4, TypeScript strict. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-04-27-dashboard-ui-redesign-design.md`

---

## File Map

| Action | Path | Purpose |
|--------|------|---------|
| CREATE | `apps/dashboard/src/app/globals.css` | Tailwind v4 import + body reset |
| CREATE | `apps/dashboard/src/app/layout.tsx` | Root layout: `<html>`, `<body>`, `AppShell` |
| CREATE | `apps/dashboard/src/components/AppShell.tsx` | Client shell: conditional sidebar by pathname |
| CREATE | `apps/dashboard/src/components/Sidebar.tsx` | 56px icon sidebar with nav + avatar |
| MODIFY | `apps/dashboard/src/app/login/page.tsx` | Clean card login design |
| MODIFY | `apps/dashboard/src/app/repos/page.tsx` | Repos page with new layout |
| MODIFY | `apps/dashboard/src/app/repos/[id]/page.tsx` | Repo detail: breadcrumb + header + quick stats |
| MODIFY | `apps/dashboard/src/app/repos/[id]/StagesView.tsx` | Loop stepper + active stage card + restyled sections |

---

## Task 1: globals.css + Root Layout

**Files:**
- Create: `apps/dashboard/src/app/globals.css`
- Create: `apps/dashboard/src/app/layout.tsx`

- [ ] **Step 1: Create globals.css**

```css
/* apps/dashboard/src/app/globals.css */
@import "tailwindcss";

*, *::before, *::after {
  box-sizing: border-box;
}

body {
  margin: 0;
}
```

- [ ] **Step 2: Create layout.tsx**

```tsx
// apps/dashboard/src/app/layout.tsx
import type { Metadata } from "next";
import { auth } from "@/auth";
import { AppShell } from "@/components/AppShell";
import "./globals.css";

export const metadata: Metadata = {
  title: "Verum",
  description: "Connect your repo. Auto-evolve your AI.",
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await auth();
  const username =
    ((session?.user as Record<string, unknown>)?.name as string)?.[0]?.toUpperCase() ?? "?";

  return (
    <html lang="en">
      <body className="bg-slate-50 text-slate-900 antialiased">
        <AppShell username={username}>{children}</AppShell>
      </body>
    </html>
  );
}
```

- [ ] **Step 3: Type-check**

```bash
cd apps/dashboard && pnpm tsc --noEmit
```

Expected: no errors related to the new files.

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/src/app/globals.css apps/dashboard/src/app/layout.tsx
git commit -m "feat(dashboard): add root layout with globals.css"
```

---

## Task 2: AppShell + Sidebar Components

**Files:**
- Create: `apps/dashboard/src/components/AppShell.tsx`
- Create: `apps/dashboard/src/components/Sidebar.tsx`

- [ ] **Step 1: Create Sidebar.tsx**

```tsx
// apps/dashboard/src/components/Sidebar.tsx
import Link from "next/link";

interface Props {
  pathname: string;
  username: string;
}

function NavItem({
  href,
  active,
  title,
  children,
}: {
  href: string;
  active: boolean;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      title={title}
      className={`flex h-9 w-9 items-center justify-center rounded-lg transition-colors ${
        active
          ? "bg-indigo-100 text-indigo-600"
          : "text-slate-400 hover:bg-slate-100 hover:text-slate-600"
      }`}
    >
      {children}
    </Link>
  );
}

export function Sidebar({ pathname, username }: Props) {
  const reposActive = pathname.startsWith("/repos") || pathname.startsWith("/analyses") || pathname.startsWith("/infer") || pathname.startsWith("/harvest") || pathname.startsWith("/generate") || pathname.startsWith("/deploy") || pathname.startsWith("/retrieve");
  const docsActive = pathname.startsWith("/docs");

  return (
    <aside className="flex h-screen w-14 flex-shrink-0 flex-col items-center border-r border-slate-200 bg-white py-3">
      {/* Logo badge */}
      <div className="mb-4 flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-500">
        <span className="text-sm font-black text-white">V</span>
      </div>

      {/* Nav items */}
      <nav className="flex flex-col gap-1">
        <NavItem href="/repos" active={reposActive} title="Repositories">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" />
            <rect x="3" y="14" width="7" height="7" /><rect x="14" y="14" width="7" height="7" />
          </svg>
        </NavItem>

        <NavItem href="/docs" active={docsActive} title="Documentation">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
            <polyline points="14 2 14 8 20 8" />
          </svg>
        </NavItem>
      </nav>

      {/* Spacer */}
      <div className="flex-1" />

      {/* User avatar */}
      <div
        className="flex h-7 w-7 items-center justify-center rounded-full bg-slate-200 text-xs font-semibold text-slate-600"
        title="Account"
      >
        {username}
      </div>
    </aside>
  );
}
```

- [ ] **Step 2: Create AppShell.tsx**

```tsx
// apps/dashboard/src/components/AppShell.tsx
"use client";

import { usePathname } from "next/navigation";
import { Sidebar } from "./Sidebar";

interface Props {
  children: React.ReactNode;
  username: string;
}

// Routes that render full-page without the sidebar shell
const NO_SHELL_PREFIXES = ["/login", "/health"];

export function AppShell({ children, username }: Props) {
  const pathname = usePathname();

  const noShell = NO_SHELL_PREFIXES.some((prefix) => pathname.startsWith(prefix));

  if (noShell) {
    return <>{children}</>;
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar pathname={pathname} username={username} />
      <main className="flex-1 overflow-auto">{children}</main>
    </div>
  );
}
```

- [ ] **Step 3: Type-check**

```bash
cd apps/dashboard && pnpm tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4: Start dev server and verify sidebar appears**

```bash
cd apps/dashboard && pnpm dev
```

Open http://localhost:3000/repos — should see the 56px white sidebar on the left with V logo, repos icon (indigo, active), docs icon (slate), and username initial at bottom. Pages render correctly inside the main area.

Open http://localhost:3000/login — should NOT see the sidebar. Full-page layout only.

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/src/components/AppShell.tsx apps/dashboard/src/components/Sidebar.tsx
git commit -m "feat(dashboard): add AppShell and icon Sidebar components"
```

---

## Task 3: Login Page Restyle

**Files:**
- Modify: `apps/dashboard/src/app/login/page.tsx`

- [ ] **Step 1: Replace login page with new design**

```tsx
// apps/dashboard/src/app/login/page.tsx
import { signIn } from "@/auth";

export default function LoginPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 p-4">
      <div className="w-full max-w-sm rounded-xl border border-slate-200 bg-white p-8 shadow-[0_4px_24px_rgba(99,102,241,0.08)]">
        {/* Logo */}
        <div className="mb-6 flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-500">
            <span className="text-sm font-black text-white">V</span>
          </div>
          <span className="text-lg font-bold text-slate-900">Verum</span>
        </div>

        {/* Headline */}
        <h1 className="mb-1 text-base font-semibold text-slate-900">Welcome back</h1>
        <p className="mb-6 text-sm text-slate-500">
          Connect your repo. Auto-evolve your AI.
        </p>

        {/* GitHub sign-in */}
        <form
          action={async () => {
            "use server";
            await signIn("github", { redirectTo: "/repos" });
          }}
        >
          <button
            type="submit"
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-[#24292f] px-4 py-2.5 text-sm font-semibold text-white transition-opacity hover:opacity-90"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
            </svg>
            Continue with GitHub
          </button>
        </form>

        {/* Disclaimer */}
        <div className="mt-5 border-t border-slate-100 pt-4">
          <p className="text-center text-xs text-slate-300">
            Not affiliated with Verum AI Platform (verumai.com).
          </p>
        </div>
      </div>
    </main>
  );
}
```

- [ ] **Step 2: Verify login page in browser**

Navigate to http://localhost:3000/login. Expected:
- Centered card on slate-50 background
- Indigo "V" badge + "Verum" wordmark
- "Welcome back" heading, subtitle text
- Dark GitHub button with GitHub SVG icon
- Disclaimer at card bottom in light gray
- NO sidebar visible

- [ ] **Step 3: Commit**

```bash
git add apps/dashboard/src/app/login/page.tsx
git commit -m "feat(dashboard): restyle login page — clean card design"
```

---

## Task 4: Repos Page Restyle

**Files:**
- Modify: `apps/dashboard/src/app/repos/page.tsx`

- [ ] **Step 1: Replace repos page**

The server actions and data-fetching logic stays identical. Only JSX/styling changes.

```tsx
// apps/dashboard/src/app/repos/page.tsx
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
```

- [ ] **Step 2: Type-check**

```bash
cd apps/dashboard && pnpm tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Verify in browser**

Open http://localhost:3000/repos. Expected:
- Sidebar visible on left with Repos icon highlighted (indigo)
- "Repositories" page heading + subtitle
- If repos exist: white cards with GitHub icon, name, monospace slug, stage pills
- GitHub picker section with search bar and repo list
- "Connect" buttons in indigo

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/src/app/repos/page.tsx
git commit -m "feat(dashboard): restyle repos page — cards, stage pills, section headers"
```

---

## Task 5: Repo Detail Page + StagesView

**Files:**
- Modify: `apps/dashboard/src/app/repos/[id]/page.tsx`
- Modify: `apps/dashboard/src/app/repos/[id]/StagesView.tsx`

- [ ] **Step 1: Restyle page.tsx (breadcrumb + header + quick stats shell)**

```tsx
// apps/dashboard/src/app/repos/[id]/page.tsx
import { notFound, redirect } from "next/navigation";
import { auth } from "@/auth";
import { getRepoStatus, getWorkerAlive, getLatestSdkPrRequest } from "@/lib/db/queries";
import StagesView from "./StagesView";
import { ActivationCard } from "@/components/repo/ActivationCard";
import type { ActivationData } from "@/components/repo/ActivationCard";

export default async function RepoDashboardPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const session = await auth();
  if (!session?.user) redirect("/login");

  const u = session.user as Record<string, unknown>;
  const userId = String(u.id ?? "");
  if (!userId) redirect("/login");

  const { id } = await params;
  const repoId = id;
  const status = await getRepoStatus(userId, repoId);
  if (!status) notFound();

  const workerAlive = await getWorkerAlive();
  const fullName = status.repo.github_url.replace("https://github.com/", "");
  const repoDisplayName = fullName.split("/")[1] ?? fullName;

  const sdkPrRequest =
    status.latestAnalysis != null
      ? await getLatestSdkPrRequest(userId, repoId)
      : null;

  const activation: ActivationData = {
    inference: status.latestInference
      ? {
          domain: status.latestInference.domain ?? null,
          tone: status.latestInference.tone ?? null,
          summary: status.latestInference.summary ?? null,
          confidence: status.latestInference.confidence ?? null,
        }
      : null,
    analysis: status.latestAnalysis
      ? {
          call_sites_count: Array.isArray(status.latestAnalysis.call_sites)
            ? (status.latestAnalysis.call_sites as unknown[]).length
            : 0,
        }
      : null,
    harvest: { chunks_count: status.harvestChunks },
    generation: status.latestGeneration
      ? {
          id: status.latestGeneration.id,
          variants_count: status.latestGeneration.variant_count,
          eval_pairs_count: status.latestGeneration.eval_count,
          rag_config: null,
        }
      : null,
    deployment: status.latestDeploymentId
      ? { id: status.latestDeploymentId, traffic_split: 0.1 }
      : null,
  };

  return (
    <div className="p-6 max-w-4xl">
      {/* Breadcrumb */}
      <p className="mb-4 text-xs text-slate-400">
        <a href="/repos" className="hover:text-indigo-500 transition-colors">Repos</a>
        <span className="mx-1">/</span>
        <span className="text-indigo-500">{repoDisplayName}</span>
      </p>

      {/* Page header */}
      <div className="mb-6 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3 min-w-0">
          <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-slate-100">
            <svg className="h-5 w-5 text-indigo-500" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
            </svg>
          </div>
          <div className="min-w-0">
            <h1 className="text-lg font-bold text-slate-900">{repoDisplayName}</h1>
            <p className="font-mono text-xs text-slate-400">
              {fullName} · {status.repo.default_branch}
            </p>
          </div>
        </div>

        <div className="flex flex-shrink-0 items-center gap-2">
          <span
            className={`flex items-center gap-1.5 text-xs font-medium ${
              workerAlive ? "text-emerald-600" : "text-red-500"
            }`}
          >
            <span className="inline-block h-2 w-2 rounded-full bg-current" />
            worker {workerAlive ? "online" : "offline"}
          </span>
        </div>
      </div>

      {/* Live stages view — stepper + active stage + stage sections */}
      <StagesView initial={status} repoId={repoId} workerAlive={workerAlive} />

      {/* Activation card — shown once analysis exists */}
      {status.latestAnalysis != null && (
        <div className="mt-6">
          <ActivationCard
            repoId={repoId}
            activation={activation}
            existingPrUrl={sdkPrRequest?.pr_url ?? null}
            existingPrNumber={sdkPrRequest?.pr_number ?? null}
          />
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Restyle StagesView.tsx — add stepper + active stage card + restyled sections**

Replace the entire file with the following. All polling logic, server actions, and data access remain identical. Only the render output changes.

```tsx
// apps/dashboard/src/app/repos/[id]/StagesView.tsx
"use client";

import { useState, useCallback } from "react";
import type { RepoStatus } from "@/lib/db/queries";
import { useAdaptivePolling } from "@/hooks/useAdaptivePolling";
import { rerunAnalyze, rerunInfer, rerunHarvest, rerunGenerate } from "./actions";
import ObserveSection from "./ObserveSection";
import ExperimentSection from "./ExperimentSection";

interface Props {
  initial: RepoStatus;
  repoId: string;
  workerAlive: boolean;
}

// Stage metadata for the stepper
const STAGES = [
  { key: "analyze", label: "ANALYZE", short: "AN" },
  { key: "infer", label: "INFER", short: "IN" },
  { key: "harvest", label: "HARVEST", short: "HA" },
  { key: "generate", label: "GENERATE", short: "GE" },
  { key: "deploy", label: "DEPLOY", short: "DE" },
  { key: "observe", label: "OBSERVE", short: "OB" },
  { key: "experiment", label: "EXPERIMENT", short: "EX" },
  { key: "evolve", label: "EVOLVE", short: "EV" },
] as const;

const STAGE_COLORS: Record<string, { dot: string; bg: string; text: string; leftBorder: string; progress: string }> = {
  analyze:    { dot: "bg-green-500",   bg: "bg-green-50",   text: "text-green-700",   leftBorder: "border-l-green-400",   progress: "bg-gradient-to-r from-green-400 to-green-500" },
  infer:      { dot: "bg-violet-500",  bg: "bg-violet-50",  text: "text-violet-700",  leftBorder: "border-l-violet-400",  progress: "bg-gradient-to-r from-violet-400 to-violet-500" },
  harvest:    { dot: "bg-amber-500",   bg: "bg-amber-50",   text: "text-amber-700",   leftBorder: "border-l-amber-400",   progress: "bg-gradient-to-r from-amber-400 to-amber-500" },
  generate:   { dot: "bg-red-500",     bg: "bg-red-50",     text: "text-red-700",     leftBorder: "border-l-red-400",     progress: "bg-gradient-to-r from-red-400 to-red-500" },
  deploy:     { dot: "bg-blue-500",    bg: "bg-blue-50",    text: "text-blue-700",    leftBorder: "border-l-blue-400",    progress: "bg-gradient-to-r from-blue-400 to-blue-500" },
  observe:    { dot: "bg-emerald-500", bg: "bg-emerald-50", text: "text-emerald-700", leftBorder: "border-l-emerald-400", progress: "bg-gradient-to-r from-emerald-400 to-emerald-500" },
  experiment: { dot: "bg-fuchsia-500", bg: "bg-fuchsia-50", text: "text-fuchsia-700", leftBorder: "border-l-fuchsia-400", progress: "bg-gradient-to-r from-fuchsia-400 to-fuchsia-500" },
  evolve:     { dot: "bg-teal-500",    bg: "bg-teal-50",    text: "text-teal-700",    leftBorder: "border-l-teal-400",    progress: "bg-gradient-to-r from-teal-400 to-teal-500" },
};

export default function StagesView({ initial, repoId, workerAlive: _workerAlive }: Props) {
  const [status, setStatus] = useState<RepoStatus>(initial);

  const {
    repo,
    latestAnalysis,
    latestInference,
    harvestChunks,
    harvestSourcesDone,
    harvestSourcesTotal,
    latestGeneration,
    latestDeploymentId,
    latestDeploymentExperimentStatus,
  } = status;

  const isRunning = (s: string | null | undefined) => s === "pending" || s === "running";

  const anyJobActive =
    isRunning(latestAnalysis?.status) ||
    isRunning(latestInference?.status) ||
    isRunning(latestGeneration?.status);

  const pollStatus = useCallback(async () => {
    const ac = new AbortController();
    try {
      const r = await fetch(`/api/repos/${repoId}/status`, {
        signal: ac.signal,
        cache: "no-store",
      });
      if (r.ok) {
        const json = (await r.json()) as { status: RepoStatus; workerAlive: boolean };
        setStatus(json.status);
      }
    } catch {
      // ignore AbortError and network errors
    }
  }, [repoId]);

  useAdaptivePolling(pollStatus, anyJobActive, {
    minIntervalMs: 2_000,
    maxIntervalMs: 30_000,
    backoffFactor: 2,
  });

  // Derive stage completion states for the stepper
  const analyzeStatus = latestAnalysis?.status ?? null;
  const inferStatus = latestInference?.status ?? null;
  const harvestDone = harvestChunks > 0 && harvestSourcesDone >= harvestSourcesTotal && harvestSourcesTotal > 0;
  const harvestRunning = !harvestDone && (harvestChunks > 0 || harvestSourcesTotal > 0);
  const generateStatus = latestGeneration?.status ?? null;
  const deployDone = !!latestDeploymentId;

  type StepState = "done" | "active" | "pending";
  const stepStates: StepState[] = [
    analyzeStatus === "done" ? "done" : isRunning(analyzeStatus) ? "active" : "pending",
    inferStatus === "done" ? "done" : isRunning(inferStatus) ? "active" : "pending",
    harvestDone ? "done" : harvestRunning ? "active" : "pending",
    generateStatus === "done" ? "done" : isRunning(generateStatus) ? "active" : "pending",
    deployDone ? "done" : "pending",
    deployDone ? "done" : "pending",
    latestDeploymentExperimentStatus && latestDeploymentExperimentStatus !== "idle" ? "done" : "pending",
    "pending",
  ];

  // Active stage key for the active stage card
  const activeStageIdx = stepStates.findIndex((s) => s === "active");
  const activeStageKey = activeStageIdx >= 0 ? STAGES[activeStageIdx].key : null;
  const activeColors = activeStageKey ? STAGE_COLORS[activeStageKey] : null;

  // Quick stats
  const callSitesCount = Array.isArray(latestAnalysis?.call_sites)
    ? (latestAnalysis.call_sites as unknown[]).length
    : null;

  return (
    <div className="space-y-4">
      {/* ── Loop Progress Stepper ── */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <p className="mb-4 text-xs font-semibold uppercase tracking-wide text-slate-400">
          Verum Loop Progress
        </p>
        <div className="flex items-center">
          {STAGES.map((stage, i) => {
            const state = stepStates[i];
            const colors = STAGE_COLORS[stage.key];
            const isLast = i === STAGES.length - 1;
            return (
              <div key={stage.key} className="flex flex-1 items-center">
                <div className="flex flex-col items-center gap-1.5">
                  {state === "done" ? (
                    <div className={`flex h-7 w-7 items-center justify-center rounded-full ${colors.dot}`}>
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3">
                        <polyline points="20 6 9 17 4 12" />
                      </svg>
                    </div>
                  ) : state === "active" ? (
                    <div className={`flex h-7 w-7 items-center justify-center rounded-full border-2 ${colors.dot.replace("bg-", "border-")} ${colors.bg}`}>
                      <span className={`h-2 w-2 animate-pulse rounded-full ${colors.dot}`} />
                    </div>
                  ) : (
                    <div className="flex h-7 w-7 items-center justify-center rounded-full border-2 border-slate-200 bg-slate-50">
                      <span className="text-[9px] font-bold text-slate-300">{i + 1}</span>
                    </div>
                  )}
                  <span
                    className={`text-center text-[9px] font-semibold leading-tight ${
                      state === "done"
                        ? colors.text
                        : state === "active"
                          ? colors.text
                          : "text-slate-300"
                    }`}
                    style={{ width: "40px" }}
                  >
                    {stage.label}
                  </span>
                </div>
                {!isLast && (
                  <div
                    className={`mb-5 h-0.5 flex-1 ${
                      stepStates[i] === "done" ? colors.dot.replace("bg-", "bg-") : "bg-slate-200"
                    }`}
                  />
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* ── Active Stage Card ── */}
      {activeStageKey && activeColors && (
        <div className={`rounded-xl border border-slate-200 border-l-4 ${activeColors.leftBorder} ${activeColors.bg} p-4`}
        >
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className={`rounded-full px-2 py-0.5 text-xs font-bold ${activeColors.bg} ${activeColors.text} border ${activeColors.border}`}>
                {STAGES[activeStageIdx].label}
              </span>
              <span className={`flex items-center gap-1.5 text-xs ${activeColors.text}`}>
                <span className={`inline-block h-1.5 w-1.5 animate-pulse rounded-full ${activeColors.dot}`} />
                Running
              </span>
            </div>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/50">
            <div className={`h-full w-1/3 rounded-full ${activeColors.progress}`} />
          </div>
        </div>
      )}

      {/* ── Quick Stats ── */}
      {(callSitesCount !== null || latestInference?.domain || harvestChunks > 0) && (
        <div className="grid grid-cols-3 gap-3">
          {callSitesCount !== null && (
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="mb-1 text-xs text-slate-400">Call Sites</p>
              <p className="text-xl font-bold text-slate-900">{callSitesCount}</p>
              <p className="mt-0.5 font-mono text-xs text-slate-500">
                {latestAnalysis?.call_sites != null &&
                  [...new Set(
                    (latestAnalysis.call_sites as Array<Record<string, unknown>>)
                      .map((c) => (typeof c.sdk === "string" ? c.sdk : null))
                      .filter((s): s is string => s !== null)
                  )].join(" · ")}
              </p>
            </div>
          )}
          {latestInference?.domain && (
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="mb-1 text-xs text-slate-400">Domain</p>
              <p className="text-sm font-bold text-violet-600">{latestInference.domain}</p>
              {latestInference.confidence != null && (
                <p className="mt-0.5 text-xs text-slate-500">
                  conf. {latestInference.confidence.toFixed(2)}
                </p>
              )}
            </div>
          )}
          {harvestChunks > 0 && (
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="mb-1 text-xs text-slate-400">Chunks</p>
              <p className="text-xl font-bold text-slate-900">{harvestChunks.toLocaleString()}</p>
              <p className="mt-0.5 text-xs text-slate-500">
                {harvestSourcesDone}/{harvestSourcesTotal} sources
              </p>
            </div>
          )}
        </div>
      )}

      {/* ── Stage Detail Sections ── */}
      <div className="space-y-3">
        <StageSection title="[1] ANALYZE" colorClass="border-l-green-400">
          {latestAnalysis ? (
            <div>
              <StageRow label="Status" value={isRunning(latestAnalysis.status) ? `${latestAnalysis.status} (running...)` : latestAnalysis.status} />
              {latestAnalysis.call_sites != null && (
                <StageRow label="Call sites" value={String((latestAnalysis.call_sites as unknown[]).length)} />
              )}
              {latestAnalysis.analyzed_at && (
                <StageRow label="Analyzed" value={new Date(latestAnalysis.analyzed_at).toLocaleString()} />
              )}
              {latestAnalysis.status === "done" && (
                <a href={`/analyses/${latestAnalysis.id}`} className="mt-2 inline-block text-xs text-green-600 hover:underline">
                  View full analysis →
                </a>
              )}
            </div>
          ) : (
            <p className="text-xs text-slate-400">No analysis yet.</p>
          )}
          <form action={rerunAnalyze.bind(null, repo.id, repo.github_url, repo.default_branch)} className="mt-3">
            <button type="submit" className="rounded-md bg-green-500 px-3 py-1.5 text-xs font-semibold text-white hover:bg-green-600 transition-colors">
              {latestAnalysis ? "Re-run ANALYZE" : "Run ANALYZE"}
            </button>
          </form>
        </StageSection>

        <StageSection title="[2] INFER" colorClass="border-l-violet-400">
          {latestInference ? (
            <div>
              <StageRow label="Status" value={isRunning(latestInference.status) ? `${latestInference.status} (running...)` : latestInference.status} />
              {latestInference.domain && <StageRow label="Domain" value={latestInference.domain} />}
              {latestInference.confidence != null && (
                <StageRow label="Confidence" value={`${(latestInference.confidence * 100).toFixed(0)}%`} />
              )}
              {latestInference.status === "done" && (
                <a href={`/infer/${latestAnalysis?.id}?inference_id=${latestInference.id}`} className="mt-2 inline-block text-xs text-violet-600 hover:underline">
                  View inference + approve sources →
                </a>
              )}
            </div>
          ) : (
            <p className="text-xs text-slate-400">
              {latestAnalysis?.status === "done" ? "Analysis complete — ready to infer." : "Run ANALYZE first."}
            </p>
          )}
          {latestAnalysis?.status === "done" && (
            <form action={rerunInfer.bind(null, repo.id, latestAnalysis.id)} className="mt-3">
              <button type="submit" className="rounded-md bg-violet-500 px-3 py-1.5 text-xs font-semibold text-white hover:bg-violet-600 transition-colors">
                {latestInference ? "Re-run INFER" : "Run INFER"}
              </button>
            </form>
          )}
        </StageSection>

        <StageSection title="[3] HARVEST" colorClass="border-l-amber-400">
          {harvestChunks > 0 ? (
            <div>
              <StageRow label="Sources" value={`${harvestSourcesDone} done / ${harvestSourcesTotal} total`} />
              <StageRow label="Chunks" value={harvestChunks.toLocaleString()} />
              {latestInference && (
                <div className="mt-2 flex gap-4">
                  <a href={`/harvest/${latestInference.id}`} className="text-xs text-amber-600 hover:underline">View harvest status →</a>
                  <a href={`/retrieve?inference_id=${latestInference.id}`} className="text-xs text-amber-600 hover:underline">Search knowledge →</a>
                </div>
              )}
            </div>
          ) : (
            <p className="text-xs text-slate-400">
              {latestInference?.status === "done" ? "Harvest in progress or no sources." : "Run INFER first."}
            </p>
          )}
          {latestInference?.status === "done" && latestAnalysis && (
            <form action={rerunHarvest.bind(null, latestInference.id, latestAnalysis.id)} className="mt-3">
              <button type="submit" className="rounded-md bg-amber-500 px-3 py-1.5 text-xs font-semibold text-white hover:bg-amber-600 transition-colors">
                {harvestChunks > 0 ? "Re-trigger HARVEST" : "Run HARVEST"}
              </button>
            </form>
          )}
        </StageSection>

        <StageSection title="[4] GENERATE" colorClass="border-l-red-400">
          {latestGeneration ? (
            <div>
              <StageRow label="Status" value={isRunning(latestGeneration.status) ? `${latestGeneration.status} (running...)` : latestGeneration.status} />
              {latestGeneration.status === "done" && (
                <>
                  <StageRow label="Prompt variants" value={String(latestGeneration.variant_count)} />
                  <StageRow label="Eval pairs" value={String(latestGeneration.eval_count)} />
                </>
              )}
            </div>
          ) : (
            <p className="text-xs text-slate-400">
              {harvestChunks > 0 ? "Generate in progress or not started." : "Complete HARVEST first."}
            </p>
          )}
          {latestInference?.status === "done" && harvestChunks > 0 && (
            <form action={rerunGenerate.bind(null, latestInference.id)} className="mt-3">
              <button type="submit" className="rounded-md bg-red-500 px-3 py-1.5 text-xs font-semibold text-white hover:bg-red-600 transition-colors">
                {latestGeneration ? "Re-run GENERATE" : "Run GENERATE"}
              </button>
            </form>
          )}
        </StageSection>

        <StageSection title="[5] RETRIEVE" colorClass="border-l-blue-400">
          {latestInference?.status === "done" && harvestChunks > 0 ? (
            <div>
              <StageRow label="Chunks available" value={harvestChunks.toLocaleString()} />
              <a href={`/retrieve?inference_id=${latestInference.id}`} className="mt-2 inline-block text-xs text-blue-600 hover:underline">
                Search knowledge →
              </a>
            </div>
          ) : (
            <p className="text-xs text-slate-400">Complete HARVEST first.</p>
          )}
        </StageSection>

        {latestDeploymentId && (
          <ObserveSection deploymentId={latestDeploymentId} />
        )}

        {latestDeploymentId &&
          latestDeploymentExperimentStatus &&
          latestDeploymentExperimentStatus !== "idle" && (
            <ExperimentSection deploymentId={latestDeploymentId} />
          )}
      </div>
    </div>
  );
}

function StageSection({
  title,
  colorClass,
  children,
}: {
  title: string;
  colorClass: string;
  children: React.ReactNode;
}) {
  // colorClass is a border-l-{color} class (e.g. "border-l-green-400")
  // border-l-4 sets width, border-slate-200 sets all border colors, colorClass overrides left color only
  return (
    <div className={`rounded-xl border-l-4 border border-slate-200 bg-white p-4 shadow-sm ${colorClass}`}>
      <h2 className="mb-3 text-xs font-bold uppercase tracking-wide text-slate-500">{title}</h2>
      {children}
    </div>
  );
}

function StageRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-3 text-xs text-slate-600 mb-1">
      <span className="w-24 flex-shrink-0 text-slate-400">{label}</span>
      <span className="font-medium">{value}</span>
    </div>
  );
}
```

- [ ] **Step 3: Type-check**

```bash
cd apps/dashboard && pnpm tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4: Verify in browser**

Open a repo detail page (e.g. http://localhost:3000/repos/[some-id]). Expected:
- Breadcrumb at top: "Repos / RepoName"
- Page header: GitHub icon badge + repo name + monospace slug/branch + worker status dot
- Loop progress stepper showing 8 stages with correct completion states
- If a stage is active: colored card with stage badge + pulse dot + progress bar
- Quick stats cards (call sites, domain, chunks) if data exists
- Stage detail sections below with colored left border, restyled buttons

- [ ] **Step 5: Run existing tests**

```bash
cd apps/dashboard && pnpm test
```

Expected: all existing tests pass (UI `.tsx` files are excluded from Jest coverage; Playwright E2E tests are unaffected by visual-only changes).

- [ ] **Step 6: Commit**

```bash
git add apps/dashboard/src/app/repos/[id]/page.tsx apps/dashboard/src/app/repos/[id]/StagesView.tsx
git commit -m "feat(dashboard): repo detail — loop stepper, active stage card, quick stats"
```

---

## Task 6: Open PR

- [ ] **Step 1: Push branch and open PR**

```bash
git push origin HEAD
gh pr create \
  --title "feat(dashboard): full UI redesign — clean light SaaS + icon sidebar" \
  --body "$(cat <<'EOF'
## Summary
- Add root layout.tsx + AppShell (conditional 56px icon sidebar for all authenticated routes)
- Add Sidebar component with Repos + Docs nav, user avatar
- Restyle login page: centered card with indigo-tinted shadow, GitHub SVG icon
- Restyle repos page: white cards, stage pills with pulse dots, section labels
- Restyle repo detail: Loop progress stepper (8 stages), active stage card, quick stats row
- All inline styles replaced with Tailwind v4 utility classes

## Design spec
docs/superpowers/specs/2026-04-27-dashboard-ui-redesign-design.md

## Test plan
- [ ] Login page: no sidebar, centered card, GitHub button works
- [ ] Repos page: sidebar visible, repo cards render, connect flow works  
- [ ] Repo detail: stepper reflects actual stage states, polling still works
- [ ] All existing Jest tests pass
- [ ] pnpm tsc --noEmit passes
EOF
)"
```

---

*Spec: `docs/superpowers/specs/2026-04-27-dashboard-ui-redesign-design.md`*
