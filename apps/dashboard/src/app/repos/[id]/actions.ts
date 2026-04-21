"use server";

import { redirect } from "next/navigation";
import { auth } from "@/auth";
import { enqueueAnalyze, enqueueInfer, enqueueHarvest } from "@/lib/db/jobs";
import { getHarvestSources } from "@/lib/db/queries";

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
  if (!session?.user) throw new Error("unauthorized");
  const uid = String((session.user as Record<string, unknown>).id ?? "");

  const { db } = await import("@/lib/db/client");
  const { sql } = await import("drizzle-orm");
  const generationId = crypto.randomUUID();
  await db.execute(
    sql`INSERT INTO generations (id, inference_id, status) VALUES (${generationId}::uuid, ${inferenceId}::uuid, 'pending')`
  );
  await db.execute(
    sql`INSERT INTO verum_jobs (kind, payload, owner_user_id, status)
        VALUES ('generate', ${JSON.stringify({ inference_id: inferenceId, generation_id: generationId })}::jsonb, ${uid}::uuid, 'queued')`
  );
}
