import { DeploymentConfigCache } from "./cache.js";
import { SafeConfigResolver } from "./_safe-resolver.js";
import type { DeploymentConfig } from "./_safe-resolver.js";

// ── Module-level singleton resolver ─────────────────────────────────────────

function _buildResolver(): SafeConfigResolver {
  const apiUrl = (process.env["VERUM_API_URL"] ?? "").replace(/\/$/, "");
  const apiKey = process.env["VERUM_API_KEY"] ?? "";
  const cache = new DeploymentConfigCache<DeploymentConfig>();
  return new SafeConfigResolver(apiUrl, apiKey, cache);
}

let _resolver: SafeConfigResolver | null = null;

function _getResolver(): SafeConfigResolver {
  if (!_resolver) _resolver = _buildResolver();
  return _resolver;
}

// ── Patch state ──────────────────────────────────────────────────────────────

let _patched = false;

// Exported for testing: allows resetting state between tests
export function _resetPatchState(): void {
  _patched = false;
  _resolver = null;
}

// ── Patch implementation ─────────────────────────────────────────────────────

type AnyFn = (...args: unknown[]) => unknown;

interface OpenAIChatParams {
  messages?: Array<{ role: string; content: string }>;
  extra_headers?: Record<string, string>;
  [key: string]: unknown;
}

async function _patchOpenAI(): Promise<void> {
  if (_patched) return;

  // Dynamic import so openai remains an optional peer dep.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let openaiModule: { default?: unknown; OpenAI?: unknown } | null = null;
  try {
    // @ts-expect-error — openai is an optional peer dep; not in devDependencies
    openaiModule = (await import("openai")) as { default?: unknown; OpenAI?: unknown };
  } catch {
    console.warn(
      "[verum] openai not installed — skipping auto-instrument patch. " +
        "Install with: npm install openai",
    );
    return;
  }

  // Resolve the OpenAI constructor (handles both CJS default export and named export)
  const OpenAIClass = (openaiModule.default ?? openaiModule.OpenAI) as
    | (new (...args: unknown[]) => unknown)
    | null
    | undefined;

  if (!OpenAIClass) {
    console.warn("[verum] Could not resolve OpenAI class from openai package — patch skipped");
    return;
  }

  // Obtain Completions prototype by instantiating a throw-away client with a dummy key.
  // We never call any method on it, we just walk the prototype chain.
  let completionsProto: Record<string, unknown> | null = null;
  try {
    const instance = new OpenAIClass({ apiKey: "dummy-verum-init" }) as {
      chat?: { completions?: object };
    };
    const completions = instance.chat?.completions;
    if (!completions || typeof (completions as { create?: unknown }).create !== "function") {
      console.warn(
        "[verum] client.chat.completions.create not found on OpenAI instance — patch skipped",
      );
      return;
    }
    completionsProto = Object.getPrototypeOf(completions) as Record<string, unknown>;
  } catch {
    console.warn("[verum] Failed to obtain Completions prototype — patch skipped");
    return;
  }

  if (typeof completionsProto["create"] !== "function") {
    console.warn(
      "[verum] Completions.prototype.create is not a function — patch skipped",
    );
    return;
  }

  const origCreate = completionsProto["create"] as AnyFn;

  completionsProto["create"] = async function wrappedCreate(
    this: unknown,
    ...args: unknown[]
  ): Promise<unknown> {
    const params = args[0] as OpenAIChatParams | undefined;

    // Extract deploymentId from extra_headers or env
    const deploymentId =
      params?.extra_headers?.["x-verum-deployment"] ??
      process.env["VERUM_DEPLOYMENT_ID"];

    if (!deploymentId || !params?.messages) {
      // No deployment context — pass through unchanged
      return origCreate.apply(this, args);
    }

    const resolver = _getResolver();

    let resolvedMessages = params.messages;
    let resolveReason = "fail_open";

    try {
      const result = await resolver.resolve(deploymentId, params.messages);
      resolvedMessages = result.messages;
      resolveReason = result.reason;
    } catch {
      // Never propagate resolver errors to the user
    }

    // Strip x-verum-deployment from extra_headers before forwarding
    const cleanedExtraHeaders = params.extra_headers
      ? Object.fromEntries(
          Object.entries(params.extra_headers).filter(
            ([k]) => k !== "x-verum-deployment",
          ),
        )
      : undefined;

    // Build patched params; omit extra_headers when empty to satisfy
    // exactOptionalPropertyTypes (cannot assign `undefined` to optional property).
    const { extra_headers: _dropped, ...paramsWithoutHeaders } = params;
    void _dropped;
    const patchedParams: OpenAIChatParams =
      cleanedExtraHeaders && Object.keys(cleanedExtraHeaders).length > 0
        ? { ...paramsWithoutHeaders, messages: resolvedMessages, extra_headers: cleanedExtraHeaders }
        : { ...paramsWithoutHeaders, messages: resolvedMessages };

    const startMs = Date.now();
    let response: unknown;
    let errorMsg: string | null = null;

    try {
      response = await origCreate.apply(this, [patchedParams, ...args.slice(1)]);
    } catch (err) {
      errorMsg = err instanceof Error ? err.message : String(err);
      throw err;
    } finally {
      // Fire-and-forget trace — never throws
      _sendTrace({
        deploymentId,
        resolveReason,
        latencyMs: Date.now() - startMs,
        error: errorMsg,
      });
    }

    return response;
  };

  _patched = true;
}

// ── Trace helper ─────────────────────────────────────────────────────────────

interface TracePayload {
  deploymentId: string;
  resolveReason: string;
  latencyMs: number;
  error: string | null;
}

function _sendTrace(payload: TracePayload): void {
  const apiUrl = (process.env["VERUM_API_URL"] ?? "").replace(/\/$/, "");
  const apiKey = process.env["VERUM_API_KEY"] ?? "";
  if (!apiUrl) return;

  fetch(`${apiUrl}/api/v1/traces`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "x-verum-api-key": apiKey },
    body: JSON.stringify({
      deployment_id: payload.deploymentId,
      resolve_reason: payload.resolveReason,
      latency_ms: payload.latencyMs,
      error: payload.error,
      source: "openai-patch",
    }),
  }).catch(() => {
    // swallow all trace errors
  });
}

// ── Public API ───────────────────────────────────────────────────────────────

/** Re-run the OpenAI prototype patch. No-op if already patched. */
export async function patchOpenAI(): Promise<void> {
  return _patchOpenAI();
}

// Auto-patch on module import (fire-and-forget)
void _patchOpenAI();
