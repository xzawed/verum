"use client";

import { useCallback, useEffect, useState } from "react";
import { z } from "zod";

export interface ActivationData {
  inference: {
    domain: string | null;
    tone: string | null;
    summary: string | null;
    confidence: number | null;
  } | null;
  analysis: { call_sites_count: number } | null;
  harvest: { chunks_count: number } | null;
  generation: {
    id: string;
    variants_count: number;
    eval_pairs_count: number;
    rag_config: object | null;
  } | null;
  deployment: {
    id: string;
    traffic_split: number;
  } | null;
}

interface ActivationCardProps {
  readonly repoId: string;
  readonly activation: ActivationData | null;
}

const ActivateResponse = z.object({
  deployment_id: z.string(),
  api_key: z.string(),
  verum_api_url: z.string(),
  error: z.string().optional(),
});

const PollResponse = z.object({
  deployment: z
    .object({
      id: z.string(),
      trace_count: z.number(),
    })
    .nullable()
    .optional(),
});

type CardState = "no-generation" | "ready" | "activated" | "waiting" | "connected";
type Tab = "python" | "nodejs";

function deriveInitialState(activation: ActivationData | null): CardState {
  if (!activation?.generation && !activation?.deployment) return "no-generation";
  if (!activation?.deployment) return "ready";
  return "waiting";
}

function fmt(n: number): string {
  return n.toLocaleString("en-US");
}

export function ActivationCard({ repoId, activation }: ActivationCardProps) {
  const [cardState, setCardState] = useState<CardState>(() =>
    deriveInitialState(activation),
  );
  const [apiKey, setApiKey] = useState<string | null>(null);
  const [deploymentId, setDeploymentId] = useState<string | null>(
    activation?.deployment?.id ?? null,
  );
  const [verumApiUrl, setVerumApiUrl] = useState<string | null>(null);
  const [traceCount, setTraceCount] = useState(0);
  const [tab, setTab] = useState<Tab>("python");
  const [activating, setActivating] = useState(false);
  const [activateError, setActivateError] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);

  // Poll for first trace when waiting
  useEffect(() => {
    if (cardState !== "waiting") return;

    const check = async () => {
      try {
        const res = await fetch(`/api/v1/activation/${repoId}`, {
          cache: "no-store",
        });
        if (!res.ok) return;
        const raw: unknown = await res.json();
        const data = PollResponse.safeParse(raw);
        if (!data.success) return;
        const tc = data.data.deployment?.trace_count ?? 0;
        if (tc > 0) {
          setTraceCount(tc);
          setCardState("connected");
        }
      } catch {
        // swallow — poll will retry
      }
    };

    void check();
    const interval = setInterval(() => void check(), 5000);
    return () => clearInterval(interval);
  }, [cardState, repoId]);

  const handleActivate = useCallback(async () => {
    setActivating(true);
    setActivateError(null);
    try {
      const res = await fetch(`/api/repos/${repoId}/activate`, { method: "POST" });
      const raw: unknown = await res.json();
      const data = ActivateResponse.safeParse(raw);
      if (!res.ok || !data.success) {
        setActivateError(
          (data.success ? data.data.error : null) ?? `HTTP ${res.status}`,
        );
        return;
      }
      setApiKey(data.data.api_key);
      setDeploymentId(data.data.deployment_id);
      setVerumApiUrl(data.data.verum_api_url);
      setCardState("activated");
    } catch (e) {
      setActivateError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setActivating(false);
    }
  }, [repoId]);

  const copy = useCallback((text: string, label: string) => {
    void navigator.clipboard.writeText(text).then(() => {
      setCopied(label);
      setTimeout(() => setCopied(null), 2000);
    });
  }, []);

  // Build summary line
  const summaryParts: string[] = [];
  if (activation?.inference?.domain) summaryParts.push(activation.inference.domain);
  if (activation?.inference?.tone) summaryParts.push(activation.inference.tone);
  if (activation?.analysis?.call_sites_count != null)
    summaryParts.push(
      `${fmt(activation.analysis.call_sites_count)} call site${activation.analysis.call_sites_count !== 1 ? "s" : ""}`,
    );
  if (activation?.harvest?.chunks_count && activation.harvest.chunks_count > 0)
    summaryParts.push(`${fmt(activation.harvest.chunks_count)} chunks`);
  if (activation?.generation?.variants_count && activation.generation.variants_count > 0)
    summaryParts.push(`${fmt(activation.generation.variants_count)} variants`);

  const effectiveDeploymentId = deploymentId ?? activation?.deployment?.id ?? null;

  const pythonEnvBlock = [
    `VERUM_API_URL=${verumApiUrl ?? "https://verum-production.up.railway.app"}`,
    `VERUM_API_KEY=${apiKey ?? "vk_..."}`,
    `VERUM_DEPLOYMENT_ID=${effectiveDeploymentId ?? "<deployment-id>"}`,
  ].join("\n");

  const nodejsEnvBlock = [
    `VERUM_API_URL=${verumApiUrl ?? "https://verum-production.up.railway.app"}`,
    `VERUM_API_KEY=${apiKey ?? "vk_..."}`,
    `VERUM_DEPLOYMENT_ID=${effectiveDeploymentId ?? "<deployment-id>"}`,
    `NODE_OPTIONS=--require @verum/sdk/auto`,
  ].join("\n");

  return (
    <section className="mt-8 rounded-lg border border-neutral-200 p-6 dark:border-neutral-800">
      <h2 className="mb-1 text-lg font-semibold">Activate Verum</h2>
      <p className="mb-5 text-sm text-neutral-500 dark:text-neutral-400">
        {summaryParts.length > 0 ? summaryParts.join(" · ") : "Analysis in progress…"}
      </p>

      {cardState === "no-generation" && (
        <p className="text-sm text-neutral-400">
          Waiting for GENERATE to complete before activation is available.
        </p>
      )}

      {cardState === "ready" && (
        <div className="flex flex-col gap-3">
          <p className="text-sm text-neutral-600 dark:text-neutral-300">
            Your prompts and RAG index are ready. Click <strong>Activate</strong> to get
            your deployment credentials — then set 3 env vars and you&apos;re live.
          </p>
          {activateError && (
            <p className="text-xs text-red-600 dark:text-red-400">Error: {activateError}</p>
          )}
          <button
            onClick={() => void handleActivate()}
            disabled={activating}
            className="w-fit rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-60 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
          >
            {activating ? "Activating…" : "Activate"}
          </button>
        </div>
      )}

      {cardState === "activated" && apiKey && (
        <div className="flex flex-col gap-4">
          <div className="rounded-md bg-amber-50 px-4 py-3 border border-amber-200 dark:bg-amber-950 dark:border-amber-800">
            <p className="text-sm font-medium text-amber-800 dark:text-amber-200">
              Copy your API key now — it won&apos;t be shown again.
            </p>
          </div>

          {/* Tabs */}
          <div className="flex gap-1 rounded-md bg-neutral-100 p-1 w-fit dark:bg-neutral-800">
            {(["python", "nodejs"] as Tab[]).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`rounded px-3 py-1 text-xs font-medium transition-colors ${
                  tab === t
                    ? "bg-white text-neutral-900 shadow-sm dark:bg-neutral-700 dark:text-white"
                    : "text-neutral-500 hover:text-neutral-700 dark:text-neutral-400"
                }`}
              >
                {t === "python" ? "Python" : "Node.js"}
              </button>
            ))}
          </div>

          {tab === "python" && (
            <EnvBlock
              install="pip install verum"
              envVars={pythonEnvBlock}
              note="verum-auto.pth instruments your OpenAI/Anthropic clients automatically at startup."
              onCopyEnv={() => copy(pythonEnvBlock, "python-env")}
              copied={copied === "python-env"}
            />
          )}

          {tab === "nodejs" && (
            <EnvBlock
              install="npm install @verum/sdk"
              envVars={nodejsEnvBlock}
              note="NODE_OPTIONS loads the SDK before your app code runs — no import needed."
              onCopyEnv={() => copy(nodejsEnvBlock, "nodejs-env")}
              copied={copied === "nodejs-env"}
            />
          )}

          <button
            onClick={() => setCardState("waiting")}
            className="w-fit rounded-md border border-neutral-300 px-4 py-2 text-sm font-medium text-neutral-700 hover:bg-neutral-50 dark:border-neutral-600 dark:text-neutral-300 dark:hover:bg-neutral-800"
          >
            Done — I&apos;ve saved these
          </button>
        </div>
      )}

      {cardState === "waiting" && (
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-2 text-sm text-neutral-500">
            <span
              aria-label="waiting"
              className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent"
            />
            Waiting for first trace…
          </div>
          {effectiveDeploymentId && (
            <p className="font-mono text-xs text-neutral-400">
              deployment: {effectiveDeploymentId}
            </p>
          )}
          <p className="text-xs text-neutral-400">
            Make an LLM call with your env vars set to see activity appear here.
          </p>
        </div>
      )}

      {cardState === "connected" && (
        <div className="flex items-start gap-3 rounded-md bg-emerald-50 px-4 py-3 border border-emerald-200 dark:bg-emerald-950 dark:border-emerald-800">
          <span className="mt-0.5 text-emerald-600 dark:text-emerald-400">✓</span>
          <div>
            <p className="text-sm font-medium text-emerald-800 dark:text-emerald-200">
              Connected
            </p>
            <p className="text-xs text-emerald-600 dark:text-emerald-400">
              Verum is receiving traces.{" "}
              {traceCount > 0 ? `${fmt(traceCount)} trace${traceCount !== 1 ? "s" : ""} received.` : ""}
            </p>
          </div>
        </div>
      )}
    </section>
  );
}

interface EnvBlockProps {
  readonly install: string;
  readonly envVars: string;
  readonly note: string;
  readonly onCopyEnv: () => void;
  readonly copied: boolean;
}

function EnvBlock({ install, envVars, note, onCopyEnv, copied }: EnvBlockProps) {
  return (
    <div className="flex flex-col gap-3">
      <div>
        <p className="mb-1 text-xs font-medium text-neutral-500 uppercase tracking-wide">
          1. Install
        </p>
        <code className="block rounded-md bg-neutral-100 px-3 py-2 font-mono text-xs text-neutral-800 dark:bg-neutral-800 dark:text-neutral-200">
          {install}
        </code>
      </div>

      <div>
        <div className="mb-1 flex items-center justify-between">
          <p className="text-xs font-medium text-neutral-500 uppercase tracking-wide">
            2. Set env vars
          </p>
          <button
            onClick={onCopyEnv}
            className="text-xs text-indigo-600 hover:text-indigo-800 dark:text-indigo-400"
          >
            {copied ? "Copied!" : "Copy all"}
          </button>
        </div>
        <pre className="rounded-md bg-neutral-100 px-3 py-2 font-mono text-xs text-neutral-800 dark:bg-neutral-800 dark:text-neutral-200 whitespace-pre-wrap break-all">
          {envVars}
        </pre>
      </div>

      <p className="text-xs text-neutral-400 italic">{note}</p>
    </div>
  );
}
