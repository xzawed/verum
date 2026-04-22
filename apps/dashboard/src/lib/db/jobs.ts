/**
 * Write operations: enqueue jobs and mutate DB state.
 * All mutations verify owner_user_id before acting.
 */
import { and, eq } from "drizzle-orm";
import { db } from "./client";
import {
  analyses,
  generations,
  harvest_sources,
  inferences,
  repos,
  verum_jobs,
} from "./schema";

// ── Repo CRUD ─────────────────────────────────────────────────

export async function createRepo(
  userId: string,
  githubUrl: string,
  branch: string = "main",
) {
  const existing = await db
    .select()
    .from(repos)
    .where(and(eq(repos.owner_user_id, userId), eq(repos.github_url, githubUrl)))
    .limit(1);
  if (existing[0]) return existing[0];

  const rows = await db
    .insert(repos)
    .values({ github_url: githubUrl, owner_user_id: userId, default_branch: branch })
    .returning();
  return rows[0]!;
}

export async function deleteRepo(userId: string, repoId: string) {
  await db
    .delete(repos)
    .where(and(eq(repos.id, repoId), eq(repos.owner_user_id, userId)));
}

// ── ANALYZE ───────────────────────────────────────────────────

export async function enqueueAnalyze(opts: {
  userId: string;
  repoId: string;
  repoUrl: string;
  branch: string;
}) {
  const analysisRows = await db
    .insert(analyses)
    .values({ repo_id: opts.repoId, status: "pending", started_at: new Date() })
    .returning();
  const analysis = analysisRows[0]!;

  await db.insert(verum_jobs).values({
    kind: "analyze",
    payload: {
      repo_url: opts.repoUrl,
      branch: opts.branch,
      repo_id: opts.repoId,
      analysis_id: analysis.id,
    },
    owner_user_id: opts.userId,
  });

  return analysis;
}

// ── INFER ─────────────────────────────────────────────────────

export async function enqueueInfer(opts: {
  userId: string;
  repoId: string;
  analysisId: string;
}) {
  const inferenceRows = await db
    .insert(inferences)
    .values({
      repo_id: opts.repoId,
      analysis_id: opts.analysisId,
      status: "pending",
    })
    .returning();
  const inference = inferenceRows[0]!;

  await db.insert(verum_jobs).values({
    kind: "infer",
    payload: { analysis_id: opts.analysisId, inference_id: inference.id },
    owner_user_id: opts.userId,
  });

  return inference;
}

// ── Source approve/reject ──────────────────────────────────────

export async function approveSource(sourceId: string) {
  await db
    .update(harvest_sources)
    .set({ status: "approved" })
    .where(eq(harvest_sources.id, sourceId));
}

export async function rejectSource(sourceId: string) {
  await db
    .update(harvest_sources)
    .set({ status: "rejected" })
    .where(eq(harvest_sources.id, sourceId));
}

// ── HARVEST ───────────────────────────────────────────────────

export async function enqueueHarvest(opts: {
  userId: string;
  inferenceId: string;
  sourcePairs: Array<{ sourceId: string; url: string }>;
}) {
  await db.insert(verum_jobs).values({
    kind: "harvest",
    payload: {
      inference_id: opts.inferenceId,
      source_ids: opts.sourcePairs.map((s) => [s.sourceId, s.url]),
    },
    owner_user_id: opts.userId,
  });
}

// ── RETRIEVE ──────────────────────────────────────────────────

export async function enqueueRetrieve(opts: {
  userId: string;
  inferenceId: string;
  query: string;
  hybrid: boolean;
  topK: number;
}): Promise<string> {
  const rows = await db
    .insert(verum_jobs)
    .values({
      kind: "retrieve",
      payload: {
        inference_id: opts.inferenceId,
        query: opts.query,
        hybrid: opts.hybrid,
        top_k: opts.topK,
      },
      owner_user_id: opts.userId,
    })
    .returning({ id: verum_jobs.id });
  return rows[0]!.id;
}

// ── GENERATE ──────────────────────────────────────────────────

export async function enqueueGenerate(opts: {
  userId: string;
  inferenceId: string;
}): Promise<{ generationId: string; jobId: string }> {
  const genRows = await db
    .insert(generations)
    .values({ inference_id: opts.inferenceId, status: "pending" })
    .returning({ id: generations.id });
  const generationId = genRows[0]!.id;

  const jobRows = await db
    .insert(verum_jobs)
    .values({
      kind: "generate",
      payload: { inference_id: opts.inferenceId, generation_id: generationId },
      owner_user_id: opts.userId,
    })
    .returning({ id: verum_jobs.id });

  return { generationId, jobId: jobRows[0]!.id };
}

export async function approveGeneration(userId: string, generationId: string): Promise<boolean> {
  const rows = await db
    .select({ g: generations })
    .from(generations)
    .innerJoin(inferences, eq(generations.inference_id, inferences.id))
    .innerJoin(analyses, eq(inferences.analysis_id, analyses.id))
    .innerJoin(repos, eq(analyses.repo_id, repos.id))
    .where(and(eq(generations.id, generationId), eq(repos.owner_user_id, userId)))
    .limit(1);

  if (!rows[0]) return false;

  await db
    .update(generations)
    .set({ status: "approved" })
    .where(eq(generations.id, generationId));
  return true;
}
