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
