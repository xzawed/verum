/**
 * Write operations: enqueue jobs and mutate DB state.
 * All mutations verify owner_user_id before acting.
 */
import { and, eq, sql } from "drizzle-orm";
import { db } from "./client";
import {
  analyses,
  deployments,
  generations,
  harvest_sources,
  inferences,
  repos,
  sdk_pr_requests,
  verum_jobs,
  type Inference,
} from "./schema";
import { getInference } from "./queries";

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
  if (!rows[0]) throw new Error("createRepo: INSERT returned no row");
  return rows[0];
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
  const analysis = analysisRows[0];
  if (!analysis) throw new Error("enqueueAnalyze: analysis INSERT returned no row");

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
  const inference = inferenceRows[0];
  if (!inference) throw new Error("enqueueInfer: inference INSERT returned no row");

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
  const row = rows[0];
  if (!row) throw new Error("enqueueRetrieve: job INSERT returned no row");
  return row.id;
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
  const genRow = genRows[0];
  if (!genRow) throw new Error("enqueueGenerate: generation INSERT returned no row");
  const generationId = genRow.id;

  const jobRows = await db
    .insert(verum_jobs)
    .values({
      kind: "generate",
      payload: { inference_id: opts.inferenceId, generation_id: generationId },
      owner_user_id: opts.userId,
    })
    .returning({ id: verum_jobs.id });
  const jobRow = jobRows[0];
  if (!jobRow) throw new Error("enqueueGenerate: job INSERT returned no row");

  return { generationId, jobId: jobRow.id };
}

// ── DEPLOY ────────────────────────────────────────────────────

export async function enqueueDeployment(opts: {
  userId: string;
  generationId: string;
}): Promise<string> {
  const rows = await db
    .insert(verum_jobs)
    .values({
      kind: "deploy",
      payload: { generation_id: opts.generationId },
      owner_user_id: opts.userId,
    })
    .returning({ id: verum_jobs.id });
  const row = rows[0];
  if (!row) throw new Error("enqueueDeployment: job INSERT returned no row");
  return row.id;
}

export async function updateDeploymentTraffic(
  userId: string,
  deploymentId: string,
  split: number,
) {
  await db
    .update(deployments)
    .set({ traffic_split: { baseline: 1 - split, variant: split }, updated_at: new Date() })
    .where(
      and(
        eq(deployments.id, deploymentId),
        sql`EXISTS (
          SELECT 1 FROM generations g
          JOIN inferences i ON i.id = g.inference_id
          JOIN analyses a ON a.id = i.analysis_id
          JOIN repos r ON r.id = a.repo_id
          WHERE g.id = ${deployments.generation_id}
            AND r.owner_user_id = ${userId}::uuid
        )`,
      ),
    );
}

export async function rollbackDeployment(userId: string, deploymentId: string) {
  await db
    .update(deployments)
    .set({
      status: "rolled_back",
      traffic_split: { baseline: 1.0, variant: 0.0 },
      updated_at: new Date(),
    })
    .where(
      and(
        eq(deployments.id, deploymentId),
        sql`EXISTS (
          SELECT 1 FROM generations g
          JOIN inferences i ON i.id = g.inference_id
          JOIN analyses a ON a.id = i.analysis_id
          JOIN repos r ON r.id = a.repo_id
          WHERE g.id = ${deployments.generation_id}
            AND r.owner_user_id = ${userId}::uuid
        )`,
      ),
    );
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

// ── INFER confirm ──────────────────────────────────────────────

export async function confirmInference(
  userId: string,
  inferenceId: string,
  overrides: {
    domain?: string | null;
    tone?: string | null;
    language?: string | null;
    user_type?: string | null;
  },
): Promise<Inference | null> {
  const existing = await getInference(userId, inferenceId);
  if (!existing) return null;

  const rows = await db
    .update(inferences)
    .set({
      domain: overrides.domain !== undefined ? overrides.domain : existing.domain,
      tone: overrides.tone !== undefined ? overrides.tone : existing.tone,
      language: overrides.language !== undefined ? overrides.language : existing.language,
      user_type: overrides.user_type !== undefined ? overrides.user_type : existing.user_type,
    })
    .where(eq(inferences.id, inferenceId))
    .returning();

  return rows[0] ?? null;
}

// ── OBSERVE ───────────────────────────────────────────────────

export async function insertTrace(opts: {
  deploymentId: string;
  variant: string;
  model: string;
  inputTokens: number;
  outputTokens: number;
  latencyMs: number;
  error: string | null;
  costUsd: string;
  spanAttributes?: Record<string, unknown>;
}): Promise<string> {
  const ownerUserId = await _getDeploymentOwner(opts.deploymentId);

  return db.transaction(async (tx) => {
    const traceRows = await tx.execute(
      sql`
        INSERT INTO traces (deployment_id, variant, created_at)
        VALUES (${opts.deploymentId}::uuid, ${opts.variant}, NOW())
        RETURNING id
      `,
    );
    const traceId = (traceRows.rows[0] as Record<string, unknown>).id as string;

    await tx.execute(
      sql`
        INSERT INTO spans (trace_id, model, input_tokens, output_tokens, latency_ms, cost_usd, error, span_attributes, started_at)
        VALUES (${traceId}::uuid, ${opts.model}, ${opts.inputTokens}, ${opts.outputTokens},
                ${opts.latencyMs}, ${opts.costUsd}::numeric, ${opts.error},
                ${opts.spanAttributes != null ? JSON.stringify(opts.spanAttributes) : null}::jsonb, NOW())
      `,
    );

    await tx.insert(verum_jobs).values({
      kind: "judge",
      payload: { trace_id: traceId, deployment_id: opts.deploymentId, variant: opts.variant },
      owner_user_id: ownerUserId,
    });

    return traceId;
  });
}

async function _getDeploymentOwner(deploymentId: string): Promise<string> {
  const rows = await db.execute(
    sql`
      SELECT r.owner_user_id
      FROM deployments d
      JOIN generations g ON g.id = d.generation_id
      JOIN inferences i ON i.id = g.inference_id
      JOIN analyses a ON a.id = i.analysis_id
      JOIN repos r ON r.id = a.repo_id
      WHERE d.id = ${deploymentId}::uuid
    `,
  );
  return ((rows.rows[0] as Record<string, unknown>)?.owner_user_id as string) ?? "";
}

export async function updateFeedback(
  deploymentId: string,
  traceId: string,
  score: number,
): Promise<boolean> {
  const result = await db.execute(
    sql`
      UPDATE traces SET user_feedback = ${score}
      WHERE id = ${traceId}::uuid AND deployment_id = ${deploymentId}::uuid
      RETURNING id
    `,
  );
  return (result.rowCount ?? 0) > 0;
}

export async function getModelPricing(
  modelName: string,
): Promise<{ input_per_1m_usd: string; output_per_1m_usd: string } | null> {
  const rows = await db.execute(
    sql`
      SELECT input_per_1m_usd::text, output_per_1m_usd::text
      FROM model_pricing WHERE model_name = ${modelName}
      ORDER BY effective_from DESC LIMIT 1
    `,
  );
  return (rows.rows[0] as Record<string, unknown> | undefined) as
    | { input_per_1m_usd: string; output_per_1m_usd: string }
    | null;
}

// ── SDK PR ────────────────────────────────────────────────────

export async function createSdkPrRequest(opts: {
  userId: string;
  repoId: string;
  analysisId: string;
  mode: "observe" | "bidirectional";
}): Promise<string> {
  const rows = await db
    .insert(sdk_pr_requests)
    .values({
      repo_id: opts.repoId,
      owner_user_id: opts.userId,
      analysis_id: opts.analysisId,
      mode: opts.mode,
      status: "pending",
    })
    .returning({ id: sdk_pr_requests.id });
  const row = rows[0];
  if (!row) throw new Error("createSdkPrRequest: INSERT returned no row");
  return row.id;
}

export async function updateSdkPrRequest(
  requestId: string,
  patch: {
    status: string;
    pr_url?: string | null;
    pr_number?: number | null;
    branch_name?: string | null;
    files_changed?: number;
    error?: string | null;
  },
): Promise<void> {
  await db
    .update(sdk_pr_requests)
    .set({ ...patch, updated_at: new Date() })
    .where(eq(sdk_pr_requests.id, requestId));
}
