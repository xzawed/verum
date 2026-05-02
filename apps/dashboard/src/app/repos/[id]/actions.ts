"use server";

import { redirect } from "next/navigation";
import { auth } from "@/auth";
import { enqueueAnalyze, enqueueGenerate, enqueueHarvest, enqueueInfer } from "@/lib/db/jobs";
import { getHarvestSources, getInference } from "@/lib/db/queries";

export async function rerunAnalyze(repoId: string, repoUrl: string, branch: string) {
  const session = await auth();
  if (!session?.user) redirect("/login");
  const uid = String((session.user as Record<string, unknown>).id ?? "");
  await enqueueAnalyze({ userId: uid, repoId, repoUrl, branch });
  redirect(`/repos/${repoId}`);
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

export async function rerunGenerate(inferenceId: string) {
  "use server";
  const session = await auth();
  if (!session?.user) redirect("/login");
  const uid = String((session.user as Record<string, unknown>).id ?? "");

  await enqueueGenerate({ userId: uid, inferenceId });

  const inference = await getInference(uid, inferenceId);
  if (!inference?.repo_id) redirect("/repos");
  redirect(`/repos/${inference.repo_id}`);
}
