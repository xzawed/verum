import { NextRequest } from "next/server";
import { validateApiKey } from "@/lib/api/validateApiKey";
import { checkRateLimitDual, getClientIp } from "@/lib/rateLimit";
import { db } from "@/lib/db/client";
import { spans, traces } from "@/lib/db/schema";

const PROVIDER_BASES: Record<string, string> = {
  openai: "https://api.openai.com",
  anthropic: "https://api.anthropic.com",
  grok: "https://api.x.ai",
};

const VERUM_HEADERS = new Set(["x-verum-api-key"]);

async function logProxyCall(opts: {
  deploymentId: string;
  provider: string;
  requestBody: string;
  responseBody: string;
  statusCode: number;
  latencyMs: number;
  targetUrl: string;
}): Promise<void> {
  let model = "unknown";
  let inputTokens = 0;
  let outputTokens = 0;

  try {
    const reqBody = JSON.parse(opts.requestBody) as Record<string, unknown>;
    model = typeof reqBody.model === "string" ? reqBody.model : "unknown";
  } catch {
    /* non-JSON body */
  }

  if (opts.statusCode === 200) {
    try {
      const respBody = JSON.parse(opts.responseBody) as Record<string, unknown>;
      const usage = respBody.usage as Record<string, number> | undefined;
      inputTokens = usage?.prompt_tokens ?? usage?.input_tokens ?? 0;
      outputTokens = usage?.completion_tokens ?? usage?.output_tokens ?? 0;
    } catch {
      /* non-JSON response */
    }
  }

  const [trace] = await db
    .insert(traces)
    .values({ deployment_id: opts.deploymentId, variant: "baseline" })
    .returning({ id: traces.id });

  await db.insert(spans).values({
    trace_id: String(trace.id),
    model,
    input_tokens: inputTokens,
    output_tokens: outputTokens,
    latency_ms: opts.latencyMs,
    cost_usd: "0",
    span_attributes: {
      provider: opts.provider,
      target_url: opts.targetUrl,
      status_code: opts.statusCode,
      via: "proxy",
    },
  });
}

async function handleProxy(
  req: NextRequest,
  path: string[],
): Promise<Response> {
  const apiKey = req.headers.get("x-verum-api-key") ?? "";
  const ip = getClientIp(req);

  const rateLimitResp = await checkRateLimitDual(apiKey.slice(0, 16), 120, ip, 200);
  if (rateLimitResp) return rateLimitResp;

  const keyResult = await validateApiKey(apiKey);
  if (!keyResult) return new Response("unauthorized", { status: 401 });

  const [provider, ...rest] = path;
  const targetBase = PROVIDER_BASES[provider ?? ""];
  if (!targetBase) {
    return new Response(
      `unknown provider "${provider}". Supported: ${Object.keys(PROVIDER_BASES).join(", ")}`,
      { status: 400 },
    );
  }

  const targetUrl = `${targetBase}/${rest.join("/")}`;
  const requestBody = await req.text();

  const forwardHeaders = new Headers();
  for (const [k, v] of req.headers.entries()) {
    if (!VERUM_HEADERS.has(k.toLowerCase()) && k.toLowerCase() !== "host") {
      forwardHeaders.set(k, v);
    }
  }

  const startMs = Date.now();
  let realResponse: Response;

  try {
    realResponse = await fetch(targetUrl, {
      method: req.method,
      headers: forwardHeaders,
      body: req.method !== "GET" && req.method !== "HEAD" ? requestBody : undefined,
    });
  } catch {
    return new Response("upstream unreachable", { status: 502 });
  }

  const latencyMs = Date.now() - startMs;
  const responseBody = await realResponse.text();

  logProxyCall({
    deploymentId: keyResult.deploymentId,
    provider: provider ?? "unknown",
    requestBody,
    responseBody,
    statusCode: realResponse.status,
    latencyMs,
    targetUrl,
  }).catch(() => {});

  const responseHeaders = new Headers(realResponse.headers);
  responseHeaders.delete("content-encoding");
  responseHeaders.delete("transfer-encoding");

  return new Response(responseBody, {
    status: realResponse.status,
    headers: responseHeaders,
  });
}

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  return handleProxy(req, (await params).path);
}

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  return handleProxy(req, (await params).path);
}
