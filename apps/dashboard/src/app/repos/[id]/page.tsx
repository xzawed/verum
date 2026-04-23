import { redirect } from "next/navigation";
import { auth } from "@/auth";
import { getRepoStatus, getWorkerAlive, getLatestSdkPrRequest } from "@/lib/db/queries";
import StagesView from "./StagesView";
import { SdkPrSection } from "@/components/repos/SdkPrSection";

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
  if (!status) redirect("/repos");

  const workerAlive = await getWorkerAlive();
  const repoName = status.repo.github_url.replace("https://github.com/", "");

  const sdkPrRequest = status.latestAnalysis?.status === "done"
    ? await getLatestSdkPrRequest(userId, repoId)
    : null;

  return (
    <main style={{ maxWidth: 840, margin: "40px auto", fontFamily: "monospace", padding: "0 16px" }}>
      <a href="/repos" style={{ fontSize: 12, color: "#666" }}>← My Repos</a>
      <h1 style={{ fontSize: 22, margin: "12px 0 4px" }}>{repoName}</h1>
      <p style={{ fontSize: 12, color: "#888", marginBottom: 32 }}>
        {status.repo.github_url} · branch: {status.repo.default_branch}
      </p>
      <StagesView initial={status} repoId={repoId} workerAlive={workerAlive} />
      {status.latestAnalysis?.status === "done" && (
        <SdkPrSection
          repoId={repoId}
          existingPrUrl={sdkPrRequest?.pr_url ?? null}
          existingPrNumber={sdkPrRequest?.pr_number ?? null}
        />
      )}
    </main>
  );
}
