import { auth } from "@/auth";
import { db } from "@/lib/db/client";
import { deployments, rag_configs, repos, traces } from "@/lib/db/schema";
import {
  countChunks,
  getLatestAnalysis,
  getLatestInference,
} from "@/lib/db/queries";
import { and, count, desc, eq, sql } from "drizzle-orm";

interface RagConfig {
  chunking_strategy: string;
  chunk_size: number;
  chunk_overlap: number;
  top_k: number;
  hybrid_alpha: number;
}

interface ActivationResponse {
  inference: {
    domain: string | null;
    tone: string | null;
    summary: string | null;
    confidence: number | null;
  } | null;
  analysis: {
    call_sites_count: number;
  } | null;
  harvest: {
    chunks_count: number;
  } | null;
  generation: {
    id: string;
    variants_count: number;
    eval_pairs_count: number;
    rag_config: RagConfig | null;
  } | null;
  deployment: {
    id: string;
    traffic_split: number;
    trace_count: number;
  } | null;
}

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ repoId: string }> },
) {
  const session = await auth();
  if (!session?.user) {
    return new Response("unauthorized", { status: 401 });
  }
  const userId = String((session.user as Record<string, unknown>).id ?? "");
  if (!userId) {
    return new Response("unauthorized", { status: 401 });
  }

  const { repoId } = await params;

  // Verify repo ownership
  const ownerCheck = await db
    .select({ id: repos.id })
    .from(repos)
    .where(and(eq(repos.id, repoId), eq(repos.owner_user_id, userId)))
    .limit(1);
  if (ownerCheck.length === 0) {
    // 404 intentional — avoid leaking repo existence to non-owners
    return new Response("not found", { status: 404 });
  }

  try {
    // Fetch analysis and inference in parallel (both only need repoId)
    const [analysis, inference] = await Promise.all([
      getLatestAnalysis(repoId),
      getLatestInference(repoId),
    ]);

    // Harvest chunk count (needs inferenceId)
    const chunksCount = inference ? await countChunks(String(inference.id)) : 0;

    // Latest generation summary (raw SQL to get counts in one round-trip)
    let generationRow: {
      id: string;
      variant_count: number;
      eval_count: number;
    } | null = null;
    if (inference) {
      const rows = await db.execute(
        sql`SELECT g.id::text,
            (SELECT COUNT(*)::int FROM prompt_variants WHERE generation_id = g.id) AS variant_count,
            (SELECT COUNT(*)::int FROM eval_pairs WHERE generation_id = g.id) AS eval_count
            FROM generations g
            WHERE g.inference_id = ${String(inference.id)}::uuid
            ORDER BY g.created_at DESC LIMIT 1`,
      );
      const row = rows.rows[0] as
        | { id: string; variant_count: number; eval_count: number }
        | undefined;
      generationRow = row ?? null;
    }

    // RAG config and deployment (both need generationId, run in parallel)
    let ragConfig: RagConfig | null = null;
    let depRow: { id: string; traffic_split: unknown } | null = null;

    if (generationRow) {
      const [ragRows, depRows] = await Promise.all([
        db
          .select({
            chunking_strategy: rag_configs.chunking_strategy,
            chunk_size: rag_configs.chunk_size,
            chunk_overlap: rag_configs.chunk_overlap,
            top_k: rag_configs.top_k,
            hybrid_alpha: rag_configs.hybrid_alpha,
          })
          .from(rag_configs)
          .where(eq(rag_configs.generation_id, generationRow.id))
          .limit(1),
        db
          .select({ id: deployments.id, traffic_split: deployments.traffic_split })
          .from(deployments)
          .where(eq(deployments.generation_id, generationRow.id))
          .orderBy(desc(deployments.created_at))
          .limit(1),
      ]);

      if (ragRows[0]) {
        ragConfig = {
          chunking_strategy: ragRows[0].chunking_strategy,
          chunk_size: ragRows[0].chunk_size,
          chunk_overlap: ragRows[0].chunk_overlap,
          top_k: ragRows[0].top_k,
          hybrid_alpha: ragRows[0].hybrid_alpha,
        };
      }

      if (depRows[0]) {
        depRow = { id: String(depRows[0].id), traffic_split: depRows[0].traffic_split };
      }
    }

    let traceCount = 0;
    if (depRow) {
      const countRows = await db
        .select({ total: count() })
        .from(traces)
        .where(eq(traces.deployment_id, depRow.id))
        .limit(1);
      traceCount = Number(countRows[0]?.total ?? 0);
    }

    // Build response — all sections nullable
    const body: ActivationResponse = {
      inference: inference
        ? {
            domain: inference.domain ?? null,
            tone: inference.tone ?? null,
            summary: inference.summary ?? null,
            confidence: inference.confidence ?? null,
          }
        : null,
      analysis: analysis
        ? {
            call_sites_count: Array.isArray(analysis.call_sites)
              ? analysis.call_sites.length
              : 0,
          }
        : null,
      harvest: inference
        ? { chunks_count: chunksCount }
        : null,
      generation: generationRow
        ? {
            id: generationRow.id,
            variants_count: generationRow.variant_count,
            eval_pairs_count: generationRow.eval_count,
            rag_config: ragConfig,
          }
        : null,
      deployment: depRow
        ? {
            id: depRow.id,
            traffic_split:
              typeof depRow.traffic_split === "object" &&
              depRow.traffic_split !== null &&
              "variant" in (depRow.traffic_split as Record<string, unknown>)
                ? Number((depRow.traffic_split as Record<string, unknown>).variant)
                : 0,
            trace_count: traceCount,
          }
        : null,
    };

    return Response.json(body, { headers: { "Cache-Control": "no-store" } });
  } catch (error) {
    console.error("[activation]", error);
    return new Response("internal error", { status: 500 });
  }
}
