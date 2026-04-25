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
  const repoName = status.repo.github_url.replace("https://github.com/", "");

  const sdkPrRequest = status.latestAnalysis != null
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
    <main style={{ maxWidth: 840, margin: "40px auto", fontFamily: "monospace", padding: "0 16px" }}>
      <a href="/repos" style={{ fontSize: 12, color: "#666" }}>← My Repos</a>
      <h1 style={{ fontSize: 22, margin: "12px 0 4px" }}>{repoName}</h1>
      <p style={{ fontSize: 12, color: "#888", marginBottom: 32 }}>
        {status.repo.github_url} · branch: {status.repo.default_branch}
      </p>
      <StagesView initial={status} repoId={repoId} workerAlive={workerAlive} />
      {status.latestAnalysis != null && (
        <ActivationCard
          repoId={repoId}
          activation={activation}
          existingPrUrl={sdkPrRequest?.pr_url ?? null}
          existingPrNumber={sdkPrRequest?.pr_number ?? null}
        />
      )}
    </main>
  );
}
