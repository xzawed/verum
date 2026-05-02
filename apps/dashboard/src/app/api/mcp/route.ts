import { NextRequest } from "next/server";
import { WebStandardStreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/webStandardStreamableHttp.js";
import { validateApiKey } from "@/lib/api/validateApiKey";
import { createMcpServer } from "@/lib/mcp/server";
import { getExperiments, getDeployment } from "@/lib/db/queries";
import { db } from "@/lib/db/client";
import { spans, traces, deployments, experiments } from "@/lib/db/schema";
import { and, avg, count, eq, desc } from "drizzle-orm";

async function getTracesForDeployment(deploymentId: string, limit = 20, userId: string) {
  const dep = await getDeployment(userId, deploymentId);
  if (!dep) return [];
  return db
    .select({
      id: traces.id,
      variant: traces.variant,
      created_at: traces.created_at,
    })
    .from(traces)
    .where(eq(traces.deployment_id, deploymentId))
    .orderBy(desc(traces.created_at))
    .limit(Math.min(limit, 100)); // guard even if caller skips server.ts clamp
}

async function getMetricsForDeployment(deploymentId: string, userId: string) {
  const dep = await getDeployment(userId, deploymentId);
  if (!dep) return { total_traces: 0, avg_latency_ms: null };
  const rows = await db
    .select({
      total: count(spans.id),
      avg_latency: avg(spans.latency_ms),
    })
    .from(spans)
    .innerJoin(traces, eq(spans.trace_id, traces.id))
    .where(eq(traces.deployment_id, deploymentId));

  const row = rows[0];
  return {
    total_traces: Number(row?.total ?? 0),
    avg_latency_ms: row?.avg_latency ? Number(row.avg_latency) : null,
  };
}

async function approveVariantForDeployment(deploymentId: string, variant: string, userId: string): Promise<Record<string, unknown>> {
  const dep = await getDeployment(userId, deploymentId);
  if (!dep) return { error: "Deployment not found or access denied" };

  const updatedExperiments = await db
    .update(experiments)
    .set({
      status: "converged",
      winner_variant: variant,
      confidence: 1.0,
      converged_at: new Date(),
    })
    .where(
      and(
        eq(experiments.deployment_id, deploymentId),
        eq(experiments.status, "running"),
      ),
    )
    .returning({ id: experiments.id });

  if (updatedExperiments.length === 0) {
    return { error: "No running experiment found for this deployment" };
  }

  await db
    .update(deployments)
    .set({
      current_baseline_variant: variant,
      traffic_split: { [variant]: 1.0 },
      experiment_status: "completed",
      updated_at: new Date(),
    })
    .where(eq(deployments.id, deploymentId));

  return { new_baseline: variant };
}

export async function POST(req: NextRequest): Promise<Response> {
  const apiKey =
    req.headers.get("authorization")?.replace(/^Bearer\s+/i, "") ??
    req.headers.get("x-verum-api-key") ??
    "";

  const keyResult = await validateApiKey(apiKey);
  if (!keyResult) return new Response("Unauthorized", { status: 401 });

  const server = createMcpServer({
    deploymentId: keyResult.deploymentId,
    getExperiments: (deploymentId) => getExperiments(keyResult.userId, deploymentId),
    getTraces: (deploymentId, limit) => getTracesForDeployment(deploymentId, limit ?? 20, keyResult.userId),
    getMetrics: (deploymentId) => getMetricsForDeployment(deploymentId, keyResult.userId),
    approveVariant: (deploymentId, variant) => approveVariantForDeployment(deploymentId, variant, keyResult.userId),
  });

  // stateless mode: no SSE session persistence
  const transport = new WebStandardStreamableHTTPServerTransport({ sessionIdGenerator: undefined });
  await server.connect(transport);
  return transport.handleRequest(req);
}
