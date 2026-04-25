import { auth } from "@/auth";
import { getModelPricing, insertTrace } from "@/lib/db/jobs";
import { getDeployment, getTraceList } from "@/lib/db/queries";
import { validateApiKey } from "@/lib/api/validateApiKey";
import { checkAndIncrementTraceQuota, FREE_LIMITS } from "@/lib/db/quota";
import { checkRateLimitDual, getClientIp } from "@/lib/rateLimit";

// POST — SDK-facing: API key auth via X-Verum-API-Key header
export async function POST(req: Request) {
  const apiKey = req.headers.get("x-verum-api-key") ?? "";
  if (!apiKey) return new Response("unauthorized", { status: 401 });

  // IP-level gate before expensive DB look-up: 200 traces/min per IP, 120 per key.
  // Quota enforcement below provides a secondary per-user bound.
  const ip = getClientIp(req);
  const ipGate = checkRateLimitDual(apiKey.slice(0, 16), 120, ip, 200);
  if (ipGate) return ipGate;

  const body = await req.json() as {
    deployment_id: string;
    variant: string;
    model: string;
    input_tokens: number;
    output_tokens: number;
    latency_ms: number;
    error?: string | null;
  };

  if (!body.model) {
    return new Response("bad request", { status: 400 });
  }

  const auth_result = await validateApiKey(apiKey);
  if (!auth_result) {
    return new Response("unauthorized", { status: 401 });
  }
  const { deploymentId, userId } = auth_result;

  // Verify deployment exists and belongs to this API key's owner BEFORE touching quota.
  // Without this check, quota increments even for requests against deleted/foreign deployments.
  const dep = await getDeployment(userId, deploymentId);
  if (!dep) {
    return new Response("deployment not found", { status: 404 });
  }

  const quotaResult = await checkAndIncrementTraceQuota(userId);
  if (quotaResult.status === "exceeded") {
    return new Response("quota exceeded", { status: 429 });
  }
  if (quotaResult.status === "warning") {
    const pct = Math.round((quotaResult.tracesUsed / FREE_LIMITS.traces) * 100);
    console.warn(
      `[QUOTA WARNING] user ${userId}: traces at ${quotaResult.tracesUsed}/${FREE_LIMITS.traces} (${pct}%) — configure SMTP_URL for email delivery`
    );
  }

  // Calculate cost
  const pricing = await getModelPricing(body.model);
  let costUsd = "0";
  if (pricing) {
    const inputCost = (body.input_tokens / 1_000_000) * Number(pricing.input_per_1m_usd);
    const outputCost = (body.output_tokens / 1_000_000) * Number(pricing.output_per_1m_usd);
    costUsd = (inputCost + outputCost).toFixed(6);
  }

  const traceId = await insertTrace({
    deploymentId,
    variant: body.variant ?? "baseline",
    model: body.model,
    inputTokens: body.input_tokens,
    outputTokens: body.output_tokens,
    latencyMs: body.latency_ms,
    error: body.error ?? null,
    costUsd,
  });
  return Response.json({ trace_id: traceId }, { status: 201 });
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
