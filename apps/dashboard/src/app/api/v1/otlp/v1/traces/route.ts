import { getDeployment } from "@/lib/db/queries";
import { getModelPricing, insertTrace } from "@/lib/db/jobs";
import { validateApiKey } from "@/lib/api/validateApiKey";
import { checkAndIncrementTraceQuota, FREE_LIMITS } from "@/lib/db/quota";
import { checkRateLimitDual, getClientIp } from "@/lib/rateLimit";

// ── OTLP JSON type helpers ────────────────────────────────────────────────────

interface OtlpAnyValue {
  stringValue?: string;
  intValue?: number | string; // JSON number or string (proto3 int64 → string)
  doubleValue?: number;
  boolValue?: boolean;
}

interface OtlpKeyValue {
  key: string;
  value: OtlpAnyValue;
}

interface OtlpSpan {
  traceId?: string;
  spanId?: string;
  name?: string;
  startTimeUnixNano?: string;
  endTimeUnixNano?: string;
  attributes?: OtlpKeyValue[];
  status?: { code?: number; message?: string };
}

interface OtlpScopeSpans {
  spans?: OtlpSpan[];
}

interface OtlpResourceSpans {
  scopeSpans?: OtlpScopeSpans[];
}

interface OtlpRequest {
  resourceSpans?: OtlpResourceSpans[];
}

// ── Attribute extraction helpers ─────────────────────────────────────────────

/**
 * Build a flat string-keyed map from an OTLP attributes array.
 * Values are kept as their unwrapped primitive for easy access.
 */
export function buildAttrMap(
  attributes: OtlpKeyValue[] | undefined,
): Record<string, unknown> {
  if (!attributes) return {};
  const map: Record<string, unknown> = {};
  for (const kv of attributes) {
    const v = kv.value;
    if (v.stringValue !== undefined) map[kv.key] = v.stringValue;
    else if (v.intValue !== undefined) map[kv.key] = Number(v.intValue);
    else if (v.doubleValue !== undefined) map[kv.key] = v.doubleValue;
    else if (v.boolValue !== undefined) map[kv.key] = v.boolValue;
    else map[kv.key] = null;
  }
  return map;
}

/** Read a string attribute. Returns undefined when missing or non-string. */
export function getStringAttr(
  map: Record<string, unknown>,
  key: string,
): string | undefined {
  const v = map[key];
  return typeof v === "string" ? v : undefined;
}

/** Read an integer attribute (intValue). Returns 0 when missing or non-numeric. */
export function getIntAttr(
  map: Record<string, unknown>,
  key: string,
): number {
  const v = map[key];
  if (typeof v === "number") return Math.round(v);
  if (typeof v === "string") {
    const n = Number(v);
    return isNaN(n) ? 0 : Math.round(n);
  }
  return 0;
}

/** Calculate latency in milliseconds from OTLP nanosecond timestamps. */
export function calcLatencyMs(
  startNs: string | undefined,
  endNs: string | undefined,
): number {
  if (!startNs || !endNs) return 0;
  const start = BigInt(startNs);
  const end = BigInt(endNs);
  if (end <= start) return 0;
  return Number((end - start) / 1_000_000n);
}

// ── Route handler ─────────────────────────────────────────────────────────────

export async function POST(req: Request): Promise<Response> {
  // ── Auth: Authorization: Bearer <api-key> ──────────────────────────────────
  const authHeader = req.headers.get("authorization") ?? "";
  const apiKey = authHeader.startsWith("Bearer ") ? authHeader.slice(7).trim() : "";
  if (!apiKey) {
    return new Response("unauthorized", { status: 401 });
  }

  // IP + key-based rate gate (same limits as existing traces route)
  const ip = getClientIp(req);
  const ipGate = await checkRateLimitDual(apiKey.slice(0, 16), 120, ip, 200);
  if (ipGate) return ipGate;

  // ── Validate API key ───────────────────────────────────────────────────────
  const authResult = await validateApiKey(apiKey);
  if (!authResult) {
    return new Response("unauthorized", { status: 401 });
  }
  const { deploymentId, userId } = authResult;

  // ── Verify deployment exists ───────────────────────────────────────────────
  const dep = await getDeployment(userId, deploymentId);
  if (!dep) {
    return new Response("deployment not found", { status: 404 });
  }

  // ── Parse OTLP body ────────────────────────────────────────────────────────
  let body: OtlpRequest;
  try {
    body = (await req.json()) as OtlpRequest;
  } catch {
    return new Response("invalid json", { status: 400 });
  }

  // Collect all spans before touching quota
  const allSpans: OtlpSpan[] = [];
  for (const rs of body.resourceSpans ?? []) {
    for (const ss of rs.scopeSpans ?? []) {
      for (const span of ss.spans ?? []) {
        allSpans.push(span);
      }
    }
  }

  if (allSpans.length === 0) {
    // Empty payload — respond 202 per OTLP spec without touching quota
    return Response.json({ partialSuccess: {} }, { status: 202 });
  }

  // ── Quota ──────────────────────────────────────────────────────────────────
  const quotaResult = await checkAndIncrementTraceQuota(userId);
  if (quotaResult.status === "exceeded") {
    return new Response("quota exceeded", { status: 429 });
  }
  if (quotaResult.status === "warning") {
    const pct = Math.round((quotaResult.tracesUsed / FREE_LIMITS.traces) * 100);
    console.warn(
      `[QUOTA WARNING] user ${userId}: traces at ${quotaResult.tracesUsed}/${FREE_LIMITS.traces} (${pct}%) — configure SMTP_URL for email delivery`,
    );
  }

  // ── Process each span ──────────────────────────────────────────────────────
  let failCount = 0;

  for (const span of allSpans) {
    try {
      const attrMap = buildAttrMap(span.attributes);

      const model = getStringAttr(attrMap, "llm.model_name") ?? "unknown";
      const inputTokens = getIntAttr(attrMap, "llm.token_count.prompt");
      const outputTokens = getIntAttr(attrMap, "llm.token_count.completion");
      const variant = getStringAttr(attrMap, "x-verum-variant") ?? "baseline";
      const latencyMs = calcLatencyMs(span.startTimeUnixNano, span.endTimeUnixNano);

      // x-verum-deployment is advisory — fall back to the validated deploymentId
      const spanDeploymentId = getStringAttr(attrMap, "x-verum-deployment");
      const resolvedDeploymentId = spanDeploymentId ?? deploymentId;

      const statusCode = getStringAttr(attrMap, "status_code");
      const error = statusCode && statusCode !== "OK" ? statusCode.slice(0, 4000) : null;

      // Field length guards
      if (model.length > 200 || variant.length > 200) {
        failCount++;
        continue;
      }

      const pricing = await getModelPricing(model);
      let costUsd = "0";
      if (pricing) {
        const inputCost = (inputTokens / 1_000_000) * Number(pricing.input_per_1m_usd);
        const outputCost = (outputTokens / 1_000_000) * Number(pricing.output_per_1m_usd);
        costUsd = (inputCost + outputCost).toFixed(6);
      }

      await insertTrace({
        deploymentId: resolvedDeploymentId,
        variant,
        model,
        inputTokens,
        outputTokens,
        latencyMs,
        error,
        costUsd,
        spanAttributes: attrMap,
      });
    } catch (err) {
      console.error("[OTLP] span processing error:", err);
      failCount++;
    }
  }

  // OTLP HTTP spec requires 202 with a partialSuccess body
  return Response.json(
    { partialSuccess: failCount > 0 ? { rejectedSpans: failCount } : {} },
    { status: 202 },
  );
}
