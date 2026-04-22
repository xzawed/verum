/**
 * Read-only Drizzle queries used by server components.
 * All queries enforce owner_user_id so users only see their own data.
 */
import { and, desc, eq, sql } from "drizzle-orm";
import { db } from "./client";
import {
  analyses,
  deployments,
  eval_pairs,
  generations,
  harvest_sources,
  inferences,
  prompt_variants,
  rag_configs,
  repos,
  users,
  verum_jobs,
  worker_heartbeat,
  type Analysis,
  type Deployment,
  type EvalPair,
  type Generation,
  type HarvestSource,
  type Inference,
  type PromptVariant,
  type RagConfig,
  type Repo,
  type VerumJob,
} from "./schema";

export type { Analysis, Deployment, EvalPair, Generation, HarvestSource, Inference, PromptVariant, RagConfig, Repo, VerumJob };

export async function getUserByGithubId(githubId: number) {
  const rows = await db.select().from(users).where(eq(users.github_id, githubId)).limit(1);
  return rows[0] ?? null;
}

export async function upsertUser(opts: {
  githubId: number;
  githubLogin: string;
  email: string | null;
  avatarUrl: string | null;
}) {
  const rows = await db
    .insert(users)
    .values({
      github_id: opts.githubId,
      github_login: opts.githubLogin,
      email: opts.email,
      avatar_url: opts.avatarUrl,
      last_login_at: new Date(),
    })
    .onConflictDoUpdate({
      target: users.github_id,
      set: {
        github_login: opts.githubLogin,
        email: opts.email,
        last_login_at: new Date(),
      },
    })
    .returning();
  return rows[0]!;
}

export async function getRepos(userId: string): Promise<Repo[]> {
  return db
    .select()
    .from(repos)
    .where(eq(repos.owner_user_id, userId))
    .orderBy(desc(repos.created_at));
}

export async function getRepo(userId: string, repoId: string): Promise<Repo | null> {
  const rows = await db
    .select()
    .from(repos)
    .where(and(eq(repos.id, repoId), eq(repos.owner_user_id, userId)))
    .limit(1);
  return rows[0] ?? null;
}

export async function getLatestAnalysis(repoId: string): Promise<Analysis | null> {
  const rows = await db
    .select()
    .from(analyses)
    .where(eq(analyses.repo_id, repoId))
    .orderBy(desc(analyses.started_at))
    .limit(1);
  return rows[0] ?? null;
}

export async function getAnalysis(
  userId: string,
  analysisId: string,
): Promise<Analysis | null> {
  // Verify ownership: analysis → repo → owner
  const rows = await db
    .select({ a: analyses })
    .from(analyses)
    .innerJoin(repos, eq(analyses.repo_id, repos.id))
    .where(and(eq(analyses.id, analysisId), eq(repos.owner_user_id, userId)))
    .limit(1);
  return rows[0]?.a ?? null;
}

export async function getLatestInference(repoId: string): Promise<Inference | null> {
  const rows = await db
    .select()
    .from(inferences)
    .where(eq(inferences.repo_id, repoId))
    .orderBy(desc(inferences.created_at))
    .limit(1);
  return rows[0] ?? null;
}

export async function getInference(
  userId: string,
  inferenceId: string,
): Promise<Inference | null> {
  const rows = await db
    .select({ i: inferences })
    .from(inferences)
    .innerJoin(analyses, eq(inferences.analysis_id, analyses.id))
    .innerJoin(repos, eq(analyses.repo_id, repos.id))
    .where(and(eq(inferences.id, inferenceId), eq(repos.owner_user_id, userId)))
    .limit(1);
  return rows[0]?.i ?? null;
}

export async function getHarvestSources(inferenceId: string): Promise<HarvestSource[]> {
  return db
    .select()
    .from(harvest_sources)
    .where(eq(harvest_sources.inference_id, inferenceId))
    .orderBy(harvest_sources.created_at);
}

export async function countChunks(inferenceId: string): Promise<number> {
  const rows = await db.execute(
    sql`SELECT COUNT(*)::int AS n FROM chunks WHERE inference_id = ${inferenceId}::uuid`,
  );
  return (rows.rows[0] as { n: number }).n ?? 0;
}

export async function getJob(jobId: string): Promise<VerumJob | null> {
  const rows = await db.select().from(verum_jobs).where(eq(verum_jobs.id, jobId)).limit(1);
  return rows[0] ?? null;
}

export async function getWorkerAlive(): Promise<boolean> {
  const rows = await db.execute(
    sql`SELECT last_seen_at FROM worker_heartbeat WHERE id = 1`,
  );
  const row = rows.rows[0] as { last_seen_at: Date } | undefined;
  if (!row) return false;
  const ageMs = Date.now() - new Date(row.last_seen_at).getTime();
  return ageMs < 90_000; // 90 s threshold
}

// Repo status summary used in repos dashboard
export interface GenerationSummary {
  id: string;
  status: string;
  generated_at: string | null;
  variant_count: number;
  eval_count: number;
}

export interface RepoStatus {
  repo: Repo;
  latestAnalysis: Analysis | null;
  latestInference: Inference | null;
  harvestChunks: number;
  harvestSourcesDone: number;
  harvestSourcesTotal: number;
  latestGeneration: GenerationSummary | null;
  latestDeploymentId: string | null;
}

async function getLatestDeploymentIdForGeneration(generationId: string): Promise<string | null> {
  const rows = await db
    .select({ id: deployments.id })
    .from(deployments)
    .where(eq(deployments.generation_id, generationId))
    .orderBy(desc(deployments.created_at))
    .limit(1);
  const row = rows[0];
  return row ? String(row.id) : null;
}

async function getLatestGenerationSummary(inferenceId: string): Promise<GenerationSummary | null> {
  const rows = await db.execute(
    sql`SELECT g.id::text, g.status, g.generated_at::text,
        (SELECT COUNT(*)::int FROM prompt_variants WHERE generation_id = g.id) AS variant_count,
        (SELECT COUNT(*)::int FROM eval_pairs WHERE generation_id = g.id) AS eval_count
        FROM generations g
        WHERE g.inference_id = ${inferenceId}::uuid
        ORDER BY g.created_at DESC LIMIT 1`,
  );
  const row = rows.rows[0] as unknown as GenerationSummary | undefined;
  return row ?? null;
}

export async function getGeneration(userId: string, generationId: string): Promise<Generation | null> {
  const rows = await db
    .select({ g: generations })
    .from(generations)
    .innerJoin(inferences, eq(generations.inference_id, inferences.id))
    .innerJoin(analyses, eq(inferences.analysis_id, analyses.id))
    .innerJoin(repos, eq(analyses.repo_id, repos.id))
    .where(and(eq(generations.id, generationId), eq(repos.owner_user_id, userId)))
    .limit(1);
  return rows[0]?.g ?? null;
}

export async function getGenerationFull(userId: string, generationId: string) {
  const gen = await getGeneration(userId, generationId);
  if (!gen) return null;

  const variants = await db
    .select()
    .from(prompt_variants)
    .where(eq(prompt_variants.generation_id, generationId))
    .orderBy(prompt_variants.created_at);

  const ragRows = await db
    .select()
    .from(rag_configs)
    .where(eq(rag_configs.generation_id, generationId))
    .limit(1);

  const pairs = await db
    .select()
    .from(eval_pairs)
    .where(eq(eval_pairs.generation_id, generationId))
    .limit(5);

  return { gen, variants, rag: ragRows[0] ?? null, pairs };
}

export async function getDeployment(userId: string, deploymentId: string) {
  const rows = await db
    .select({ d: deployments })
    .from(deployments)
    .innerJoin(generations, eq(deployments.generation_id, generations.id))
    .innerJoin(inferences, eq(generations.inference_id, inferences.id))
    .innerJoin(analyses, eq(inferences.analysis_id, analyses.id))
    .innerJoin(repos, eq(analyses.repo_id, repos.id))
    .where(and(eq(deployments.id, deploymentId), eq(repos.owner_user_id, userId)))
    .limit(1);
  return rows[0]?.d ?? null;
}

export async function getVariantPrompt(deploymentId: string): Promise<string | null> {
  const rows = await db.execute(
    sql`SELECT pv.content FROM deployments d
        JOIN generations g ON g.id = d.generation_id
        JOIN prompt_variants pv ON pv.generation_id = g.id
        WHERE d.id = ${deploymentId}::uuid AND pv.variant_type = 'cot'
        LIMIT 1`,
  );
  const row = rows.rows[0] as { content: string } | undefined;
  return row?.content ?? null;
}

export async function getLatestGeneration(inferenceId: string): Promise<Generation | null> {
  const rows = await db
    .select()
    .from(generations)
    .where(eq(generations.inference_id, inferenceId))
    .orderBy(desc(generations.created_at))
    .limit(1);
  return rows[0] ?? null;
}

export async function getRepoStatus(userId: string, repoId: string): Promise<RepoStatus | null> {
  const repo = await getRepo(userId, repoId);
  if (!repo) return null;

  const latestAnalysis = await getLatestAnalysis(repoId);
  const latestInference = await getLatestInference(repoId);

  let harvestChunks = 0;
  let harvestSourcesDone = 0;
  let harvestSourcesTotal = 0;
  if (latestInference) {
    const sources = await getHarvestSources(latestInference.id);
    harvestSourcesTotal = sources.length;
    harvestSourcesDone = sources.filter((s) => s.status === "done").length;
    harvestChunks = await countChunks(latestInference.id);
  }

  let latestGeneration: GenerationSummary | null = null;
  if (latestInference?.status === "done") {
    latestGeneration = await getLatestGenerationSummary(String(latestInference.id));
  }

  let latestDeploymentId: string | null = null;
  if (latestGeneration?.status === "done") {
    latestDeploymentId = await getLatestDeploymentIdForGeneration(latestGeneration.id);
  }

  return {
    repo,
    latestAnalysis,
    latestInference,
    harvestChunks,
    harvestSourcesDone,
    harvestSourcesTotal,
    latestGeneration,
    latestDeploymentId,
  };
}

// ── OBSERVE ───────────────────────────────────────────────────

export async function getTraceList(
  deploymentId: string,
  page: number = 1,
  limit: number = 20,
) {
  const offset = (page - 1) * limit;
  const rows = await db.execute(
    sql`
      SELECT
        t.id, t.variant, t.user_feedback, t.judge_score, t.created_at,
        s.latency_ms, s.cost_usd, s.model, s.input_tokens, s.output_tokens, s.error
      FROM traces t
      JOIN spans s ON s.trace_id = t.id
      WHERE t.deployment_id = ${deploymentId}::uuid
      ORDER BY t.created_at DESC
      LIMIT ${limit} OFFSET ${offset}
    `,
  );

  const countRow = await db.execute(
    sql`SELECT COUNT(*)::int AS total FROM traces WHERE deployment_id = ${deploymentId}::uuid`,
  );

  return {
    traces: rows.rows,
    total: Number((countRow.rows[0] as Record<string, unknown>)?.total ?? 0),
    page,
  };
}

export async function getTraceDetail(userId: string, traceId: string) {
  const traceRows = await db.execute(
    sql`
      SELECT
        t.id, t.variant, t.user_feedback, t.judge_score, t.created_at,
        s.latency_ms, s.cost_usd, s.model, s.input_tokens, s.output_tokens, s.error,
        jp.raw_response AS judge_raw_response, jp.judged_at
      FROM traces t
      JOIN spans s ON s.trace_id = t.id
      LEFT JOIN judge_prompts jp ON jp.trace_id = t.id
      JOIN deployments d ON d.id = t.deployment_id
      JOIN generations g ON g.id = d.generation_id
      JOIN inferences i ON i.id = g.inference_id
      JOIN analyses a ON a.id = i.analysis_id
      JOIN repos r ON r.id = a.repo_id
      WHERE t.id = ${traceId}::uuid
        AND r.owner_user_id = ${userId}::uuid
    `,
  );
  return traceRows.rows[0] ?? null;
}

export async function getDailyMetrics(deploymentId: string, days: number = 7) {
  const rows = await db.execute(
    sql`
      SELECT
        DATE(t.created_at AT TIME ZONE 'UTC')::text AS date,
        COALESCE(SUM(s.cost_usd), 0)::float AS total_cost_usd,
        COUNT(t.id)::int AS call_count,
        COALESCE(
          PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY s.latency_ms), 0
        )::int AS p95_latency_ms,
        AVG(t.judge_score)::float AS avg_judge_score
      FROM traces t
      JOIN spans s ON s.trace_id = t.id
      WHERE t.deployment_id = ${deploymentId}::uuid
        AND t.created_at >= NOW() - (${days} || ' days')::interval
      GROUP BY DATE(t.created_at AT TIME ZONE 'UTC')
      ORDER BY date ASC
    `,
  );
  return rows.rows;
}
