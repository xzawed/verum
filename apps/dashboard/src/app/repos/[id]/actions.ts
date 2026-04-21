"use server";

import { redirect } from "next/navigation";
import { auth } from "@/auth";
import { enqueueAnalyze, enqueueInfer, enqueueHarvest } from "@/lib/db/jobs";
import { getHarvestSources } from "@/lib/db/queries";

export async function rerunAnalyze(repoId: string, repoUrl: string, branch: string) {
  const session = await auth();
  if (!session?.user) redirect("/login");
  const uid = String((session.user as Record<string, unknown>).id ?? "");
  const analysis = await enqueueAnalyze({ userId: uid, repoId, repoUrl, branch });
  redirect(`/analyses/${analysis.id}`);
}

export async function rerunInfer(repoId: string, analysisId: string) {
  const session = await auth();
  if (!session?.user) redirect("/login");
  const uid = String((session.user as Record<string, unknown>).id ?? "");
  const inference = await enqueueInfer({ userId: uid, repoId, analysisId });
  redirect(`/infer/${analysisId}?inference_id=${inference.id}`);
}

export async function rerunHarvest(inferenceId: string, analysisId: string) {
  const session = await auth();
  if (!session?.user) redirect("/login");
  const uid = String((session.user as Record<string, unknown>).id ?? "");
  const sources = await getHarvestSources(inferenceId);
  const approved = sources.filter((src) => src.status === "approved");
  if (approved.length === 0) redirect(`/infer/${analysisId}?inference_id=${inferenceId}`);
  await enqueueHarvest({
    userId: uid,
    inferenceId,
    sourcePairs: approved.map((src) => ({ sourceId: src.id, url: src.url })),
  });
  redirect(`/harvest/${inferenceId}`);
}
