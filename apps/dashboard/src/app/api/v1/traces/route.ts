import { auth } from "@/auth";
import { getModelPricing, insertTrace } from "@/lib/db/jobs";
import { getDeployment, getTraceList } from "@/lib/db/queries";

// POST — SDK-facing: API key auth via X-Verum-API-Key header
export async function POST(req: Request) {
  const apiKey = req.headers.get("x-verum-api-key") ?? "";
  if (!apiKey) return new Response("unauthorized", { status: 401 });

  const body = await req.json() as {
    deployment_id: string;
    variant: string;
    model: string;
    input_tokens: number;
    output_tokens: number;
    latency_ms: number;
    error?: string | null;
  };

  if (!body.deployment_id || !body.model) {
    return new Response("bad request", { status: 400 });
  }

  // API key is the deployment_id (simple auth for Phase 4-A)
  if (apiKey !== body.deployment_id) {
    return new Response("unauthorized", { status: 401 });
  }

  // Calculate cost
  const pricing = await getModelPricing(body.model);
  let costUsd = "0";
  if (pricing) {
    const inputCost = (body.input_tokens / 1_000_000) * Number(pricing.input_per_1m_usd);
    const outputCost = (body.output_tokens / 1_000_000) * Number(pricing.output_per_1m_usd);
    costUsd = (inputCost + outputCost).toFixed(6);
  }

  try {
    const traceId = await insertTrace({
      deploymentId: body.deployment_id,
      variant: body.variant ?? "baseline",
      model: body.model,
      inputTokens: body.input_tokens,
      outputTokens: body.output_tokens,
      latencyMs: body.latency_ms,
      error: body.error ?? null,
      costUsd,
    });
    return Response.json({ trace_id: traceId }, { status: 201 });
  } catch {
    return new Response("deployment not found", { status: 404 });
  }
}

// GET — browser-facing: Auth.js session
export async function GET(req: Request) {
  const session = await auth();
  if (!session?.user) return new Response("unauthorized", { status: 401 });

  const { searchParams } = new URL(req.url);
  const deploymentId = searchParams.get("deployment_id") ?? "";
  const page = Number(searchParams.get("page") ?? "1");
  const limit = Number(searchParams.get("limit") ?? "20");

  if (!deploymentId) return new Response("deployment_id required", { status: 400 });

  const userId = session.user.id as string;
  const dep = await getDeployment(userId, deploymentId);
  if (!dep) return new Response("not found", { status: 404 });

  const result = await getTraceList(deploymentId, page, limit);
  return Response.json(result, { headers: { "Cache-Control": "no-store" } });
}
