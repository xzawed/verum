"use client";

import { motion, AnimatePresence } from "framer-motion";
import { useCallback, useEffect, useState } from "react";
import { z } from "zod";
import { useLocale } from "@/context/LocaleContext";
import { t } from "@/lib/i18n";

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

  const { locale } = useLocale();

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
      <h2 className="mb-1 text-lg font-semibold">{t("activation", "title", locale)}</h2>
      <p className="mb-5 text-sm text-neutral-500 dark:text-neutral-400">
        {summaryParts.length > 0 ? summaryParts.join(" · ") : t("activation", "analysisInProgress", locale)}
      </p>

      <AnimatePresence mode="wait">
        {cardState === "no-generation" && (
          <motion.p
            key="no-generation"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="text-sm text-neutral-400"
          >
            {t("activation", "noGeneration", locale)}
          </motion.p>
        )}

        {cardState === "ready" && (
          <motion.div
            key="ready"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.25 }}
            className="flex flex-col gap-3"
          >
            <p className="text-sm text-neutral-600 dark:text-neutral-300">
              {t("activation", "readyDesc", locale)}
            </p>
            {activateError && (
              <p className="text-xs text-red-600 dark:text-red-400">
                {t("activation", "errorPrefix", locale)}{activateError}
              </p>
            )}
            <motion.button
              whileTap={{ scale: 0.95 }}
              onClick={() => void handleActivate()}
              disabled={activating}
              className="w-fit rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-60 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
            >
              {activating ? t("common", "activating", locale) : t("common", "activate", locale)}
            </motion.button>
          </motion.div>
        )}

        {cardState === "activated" && apiKey && (
          <motion.div
            key="activated"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.3 }}
            className="flex flex-col gap-4"
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.97 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.1, duration: 0.25 }}
              className="rounded-md bg-amber-50 px-4 py-3 border border-amber-200 dark:bg-amber-950 dark:border-amber-800"
            >
              <p className="text-sm font-medium text-amber-800 dark:text-amber-200">
                {t("activation", "apiKeyCopyNow", locale)}
              </p>
            </motion.div>

            {/* Tabs */}
            <div className="flex gap-1 rounded-md bg-neutral-100 p-1 w-fit dark:bg-neutral-800">
              {(["python", "nodejs"] as Tab[]).map((tabKey) => (
                <button
                  key={tabKey}
                  onClick={() => setTab(tabKey)}
                  className={`rounded px-3 py-1 text-xs font-medium transition-colors ${
                    tab === tabKey
                      ? "bg-white text-neutral-900 shadow-sm dark:bg-neutral-700 dark:text-white"
                      : "text-neutral-500 hover:text-neutral-700 dark:text-neutral-400"
                  }`}
                >
                  {tabKey === "python" ? "Python" : "Node.js"}
                </button>
              ))}
            </div>

            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2, duration: 0.25 }}
            >
              {tab === "python" && (
                <EnvBlock
                  install="pip install verum"
                  envVars={pythonEnvBlock}
                  installLabel={t("activation", "install", locale)}
                  envLabel={t("activation", "setEnvVars", locale)}
                  note={t("activation", "sdkNoteAutoInst", locale)}
                  copyLabel={t("common", "copyAll", locale)}
                  copiedLabel={t("common", "copied", locale)}
                  onCopyEnv={() => copy(pythonEnvBlock, "python-env")}
                  copied={copied === "python-env"}
                />
              )}
              {tab === "nodejs" && (
                <EnvBlock
                  install="npm install @verum/sdk"
                  envVars={nodejsEnvBlock}
                  installLabel={t("activation", "install", locale)}
                  envLabel={t("activation", "setEnvVars", locale)}
                  note={t("activation", "sdkNoteNodeOpts", locale)}
                  copyLabel={t("common", "copyAll", locale)}
                  copiedLabel={t("common", "copied", locale)}
                  onCopyEnv={() => copy(nodejsEnvBlock, "nodejs-env")}
                  copied={copied === "nodejs-env"}
                />
              )}
            </motion.div>

            <button
              onClick={() => setCardState("waiting")}
              className="w-fit rounded-md border border-neutral-300 px-4 py-2 text-sm font-medium text-neutral-700 hover:bg-neutral-50 dark:border-neutral-600 dark:text-neutral-300 dark:hover:bg-neutral-800"
            >
              {t("activation", "doneSaved", locale)}
            </button>
          </motion.div>
        )}

        {cardState === "waiting" && (
          <motion.div
            key="waiting"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="flex flex-col gap-3"
          >
            <div className="flex items-center gap-3 text-sm text-neutral-500">
              {/* Multi-ring spinner */}
              <div className="relative flex h-5 w-5 flex-shrink-0 items-center justify-center">
                <span className="absolute inset-0 rounded-full border-2 border-indigo-300 animate-breathe opacity-50" />
                <span className="absolute inset-1 rounded-full border-2 border-indigo-400 animate-breathe opacity-75" style={{ animationDelay: "0.3s" }} />
                <span className="h-1.5 w-1.5 rounded-full bg-indigo-500 animate-pulse" />
              </div>
              {t("activation", "waitingForTrace", locale)}
            </div>
            {effectiveDeploymentId && (
              <p className="font-mono text-xs text-neutral-400">
                {t("activation", "deployment", locale)}: {effectiveDeploymentId}
              </p>
            )}
            <p className="text-xs text-neutral-400">
              {t("activation", "makeAnLlmCall", locale)}
            </p>
          </motion.div>
        )}

        {cardState === "connected" && (
          <motion.div
            key="connected"
            initial={{ opacity: 0, scale: 0.95, y: 4 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ type: "spring", stiffness: 400, damping: 25 }}
            className="flex items-start gap-3 rounded-md bg-emerald-50 px-4 py-3 border border-emerald-200 dark:bg-emerald-950 dark:border-emerald-800"
          >
            <span className="mt-0.5 text-emerald-600 dark:text-emerald-400">✓</span>
            <div>
              <p className="text-sm font-medium text-emerald-800 dark:text-emerald-200">
                {t("common", "connected", locale)}
              </p>
              <p className="text-xs text-emerald-600 dark:text-emerald-400">
                {t("activation", "tracesReceived", locale)}{" "}
                {traceCount > 0 ? `${fmt(traceCount)} trace${traceCount !== 1 ? "s" : ""} received.` : ""}
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}

interface EnvBlockProps {
  readonly install: string;
  readonly envVars: string;
  readonly installLabel: string;
  readonly envLabel: string;
  readonly note: string;
  readonly copyLabel: string;
  readonly copiedLabel: string;
  readonly onCopyEnv: () => void;
  readonly copied: boolean;
}

function EnvBlock({ install, envVars, installLabel, envLabel, note, copyLabel, copiedLabel, onCopyEnv, copied }: EnvBlockProps) {
  return (
    <div className="flex flex-col gap-3">
      <div>
        <p className="mb-1 text-xs font-medium text-neutral-500 uppercase tracking-wide">
          {installLabel}
        </p>
        <code className="block rounded-md bg-neutral-100 px-3 py-2 font-mono text-xs text-neutral-800 dark:bg-neutral-800 dark:text-neutral-200">
          {install}
        </code>
      </div>

      <div>
        <div className="mb-1 flex items-center justify-between">
          <p className="text-xs font-medium text-neutral-500 uppercase tracking-wide">
            {envLabel}
          </p>
          <button
            onClick={onCopyEnv}
            className="text-xs text-indigo-600 hover:text-indigo-800 dark:text-indigo-400"
          >
            {copied ? copiedLabel : copyLabel}
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
