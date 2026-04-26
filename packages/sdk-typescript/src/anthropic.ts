/**
 * Zero-invasive Anthropic integration for Verum.
 *
 * Importing this module is the *only* change needed in a user's service:
 *
 *   import "@verum/sdk/anthropic"; // patches Anthropic SDK automatically
 *
 * After import, all `new Anthropic().messages.create()` calls are
 * transparently intercepted. Verum reads the deployment config (with a
 * 5-layer safety net), optionally swaps the system prompt, then fires an
 * async background trace — without changing the call signature.
 *
 * The Anthropic SDK places the system prompt in a top-level `system`
 * parameter (not inside the `messages` array). Verum synthesises a
 * [{role:"system",content:...}] array to pass through the resolver,
 * then extracts any modified system prompt back out.
 *
 * Environment variables:
 *   VERUM_API_URL         — Base URL of the Verum API.
 *   VERUM_API_KEY         — Your Verum API key.
 *   VERUM_DEPLOYMENT_ID   — Default deployment ID (overridden by
 *                            x-verum-deployment in extra_headers).
 */

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

export function _resetPatchState(): void {
  _patched = false;
  _resolver = null;
}

// ── System-prompt helpers ────────────────────────────────────────────────────

interface ChatMessage {
  role: string;
  content: string;
}

/** Wrap an Anthropic top-level system string into a synthetic messages array. */
function _buildSyntheticMessages(system: string): ChatMessage[] {
  if (!system) return [];
  return [{ role: "system", content: system }];
}

/** Extract system prompt back out of a (possibly modified) messages array. */
function _extractSystem(messages: ChatMessage[]): string {
  const sys = messages.find((m) => m.role === "system");
  return sys?.content ?? "";
}

// ── Trace helper ─────────────────────────────────────────────────────────────

interface AnthropicTracePayload {
  deploymentId: string;
  variant: string;
  model: string | null;
  inputTokens: number | null;
  outputTokens: number | null;
  latencyMs: number;
  error: string | null;
}

function _sendTrace(payload: AnthropicTracePayload): void {
  const apiUrl = (process.env["VERUM_API_URL"] ?? "").replace(/\/$/, "");
  const apiKey = process.env["VERUM_API_KEY"] ?? "";
  if (!apiUrl) return;

  fetch(`${apiUrl}/api/v1/traces`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "x-verum-api-key": apiKey },
    body: JSON.stringify({
      deployment_id: payload.deploymentId,
      variant: payload.variant,
      model: payload.model,
      input_tokens: payload.inputTokens,
      output_tokens: payload.outputTokens,
      latency_ms: payload.latencyMs,
      error: payload.error,
    }),
  }).catch(() => {
    // swallow all trace errors — never propagate to user
  });
}

// ── Patch implementation ─────────────────────────────────────────────────────

type AnyFn = (...args: unknown[]) => unknown;

interface AnthropicMessageParams {
  system?: string;
  messages?: ChatMessage[];
  model?: string;
  extra_headers?: Record<string, string>;
  [key: string]: unknown;
}

interface AnthropicUsage {
  input_tokens?: number;
  output_tokens?: number;
}

interface AnthropicResponse {
  model?: string;
  usage?: AnthropicUsage;
}

async function _patchAnthropic(): Promise<void> {
  if (_patched) return;

  // Dynamic import so @anthropic-ai/sdk remains an optional peer dep.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let anthropicModule: { default?: unknown; Anthropic?: unknown } | null = null;
  try {
    // @ts-expect-error — @anthropic-ai/sdk is an optional peer dep; not in devDependencies
    anthropicModule = (await import("@anthropic-ai/sdk")) as { default?: unknown; Anthropic?: unknown };
  } catch {
    console.warn(
      "[verum] @anthropic-ai/sdk not installed — skipping auto-instrument patch. " +
        "Install with: npm install @anthropic-ai/sdk",
    );
    return;
  }

  const AnthropicClass = (anthropicModule.default ?? anthropicModule.Anthropic) as
    | (new (...args: unknown[]) => unknown)
    | null
    | undefined;

  if (!AnthropicClass) {
    console.warn("[verum] Could not resolve Anthropic class — patch skipped");
    return;
  }

  // Obtain messages prototype via a throw-away instance.
  let messagesProto: Record<string, unknown> | null = null;
  try {
    const instance = new AnthropicClass({ apiKey: "dummy-verum-init" }) as {
      messages?: object;
    };
    const messages = instance.messages;
    if (!messages || typeof (messages as { create?: unknown }).create !== "function") {
      console.warn("[verum] client.messages.create not found on Anthropic instance — patch skipped");
      return;
    }
    messagesProto = Object.getPrototypeOf(messages) as Record<string, unknown>;
  } catch {
    console.warn("[verum] Failed to obtain Anthropic Messages prototype — patch skipped");
    return;
  }

  if (typeof messagesProto["create"] !== "function") {
    console.warn("[verum] Anthropic Messages.prototype.create is not a function — patch skipped");
    return;
  }

  const origCreate = messagesProto["create"] as AnyFn;

  messagesProto["create"] = async function wrappedCreate(
    this: unknown,
    ...args: unknown[]
  ): Promise<unknown> {
    const params = args[0] as AnthropicMessageParams | undefined;

    const deploymentId =
      params?.extra_headers?.["x-verum-deployment"] ??
      process.env["VERUM_DEPLOYMENT_ID"];

    if (!deploymentId) {
      return origCreate.apply(this, args);
    }

    const resolver = _getResolver();

    const systemText = params?.system ?? "";
    let resolvedSystem = systemText;
    let variant = "fail_open";

    try {
      const synthetic = _buildSyntheticMessages(systemText);
      if (synthetic.length > 0) {
        const result = await resolver.resolve(deploymentId, synthetic);
        resolvedSystem = _extractSystem(result.messages) || systemText;
        variant = result.reason;
      }
    } catch {
      // Never propagate resolver errors to the user
    }

    // Strip x-verum-deployment before forwarding to Anthropic
    const cleanedExtraHeaders = params?.extra_headers
      ? Object.fromEntries(
          Object.entries(params.extra_headers).filter(([k]) => k !== "x-verum-deployment"),
        )
      : undefined;

    const { extra_headers: _dropped, system: _sys, ...paramsWithoutHeaders } = params ?? {};
    void _dropped;
    void _sys;
    const patchedParams: AnthropicMessageParams = {
      ...paramsWithoutHeaders,
      system: resolvedSystem || undefined,
      ...(cleanedExtraHeaders && Object.keys(cleanedExtraHeaders).length > 0
        ? { extra_headers: cleanedExtraHeaders }
        : {}),
    };

    const startMs = Date.now();
    let response: unknown;
    let errorMsg: string | null = null;

    try {
      response = await origCreate.apply(this, [patchedParams, ...args.slice(1)]);
    } catch (err) {
      errorMsg = err instanceof Error ? err.message : String(err);
      throw err;
    } finally {
      const resp = response as AnthropicResponse | undefined;
      _sendTrace({
        deploymentId,
        variant,
        model: resp?.model ?? params?.model ?? null,
        inputTokens: resp?.usage?.input_tokens ?? null,
        outputTokens: resp?.usage?.output_tokens ?? null,
        latencyMs: Date.now() - startMs,
        error: errorMsg,
      });
    }

    return response;
  };

  _patched = true;
}

// ── Public API ───────────────────────────────────────────────────────────────

/** Re-run the Anthropic prototype patch. No-op if already patched. */
export async function patchAnthropic(): Promise<void> {
  return _patchAnthropic();
}

// Auto-patch on module import (fire-and-forget)
void _patchAnthropic();
