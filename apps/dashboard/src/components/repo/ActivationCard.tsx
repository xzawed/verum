"use client";

import { useState } from "react";
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
  deployment: { id: string; traffic_split: number } | null;
}

interface ActivationCardProps {
  readonly repoId: string;
  readonly activation: ActivationData | null;
  readonly existingPrUrl?: string | null;
  readonly existingPrNumber?: number | null;
  readonly existingBidirectionalPrUrl?: string | null;
  readonly existingBidirectionalPrNumber?: number | null;
}

const SdkPrResponse = z.object({
  pr_url: z.string().optional(),
  pr_number: z.number().optional(),
  files_changed: z.number().optional(),
  message: z.string().optional(),
  error: z.string().optional(),
});

type ButtonState =
  | "idle"
  | "loading"
  | { prUrl: string; prNumber: number }
  | { alreadyDone: true }
  | { error: string };

function fmt(n: number): string {
  return n.toLocaleString("en-US");
}

export function ActivationCard({
  repoId,
  activation,
  existingPrUrl,
  existingPrNumber,
  existingBidirectionalPrUrl,
  existingBidirectionalPrNumber,
}: ActivationCardProps) {
  const initialObserve =
    existingPrUrl != null && existingPrNumber != null
      ? ({ prUrl: existingPrUrl, prNumber: existingPrNumber } as ButtonState)
      : ("idle" as ButtonState);

  const initialBidirectional =
    existingBidirectionalPrUrl != null && existingBidirectionalPrNumber != null
      ? ({ prUrl: existingBidirectionalPrUrl, prNumber: existingBidirectionalPrNumber } as ButtonState)
      : ("idle" as ButtonState);

  const [observeState, setObserveState] = useState<ButtonState>(initialObserve);
  const [bidirectionalState, setBidirectionalState] = useState<ButtonState>(initialBidirectional);

  async function handlePr(mode: "observe" | "bidirectional") {
    const setState = mode === "observe" ? setObserveState : setBidirectionalState;
    setState("loading");
    try {
      const res = await fetch(`/api/repos/${repoId}/sdk-pr?mode=${mode}`, {
        method: "POST",
      });
      const raw: unknown = await res.json();
      const data = SdkPrResponse.parse(raw);
      if (!res.ok) {
        setState({ error: data.error ?? `HTTP ${res.status}` });
        return;
      }
      if (!data.pr_url || !data.pr_number) {
        setState({ alreadyDone: true });
        return;
      }
      setState({ prUrl: data.pr_url, prNumber: data.pr_number });
    } catch (e) {
      setState({ error: e instanceof Error ? e.message : "Unknown error" });
    }
  }

  // Build summary parts
  const summaryParts: string[] = [];
  if (activation?.inference?.domain) summaryParts.push(activation.inference.domain);
  if (activation?.inference?.tone) summaryParts.push(activation.inference.tone);
  if (activation?.analysis?.call_sites_count != null)
    summaryParts.push(`${fmt(activation.analysis.call_sites_count)} call site${activation.analysis.call_sites_count !== 1 ? "s" : ""}`);
  if (activation?.harvest?.chunks_count != null && activation.harvest.chunks_count > 0)
    summaryParts.push(`${fmt(activation.harvest.chunks_count)} chunks`);
  if (activation?.generation?.variants_count != null && activation.generation.variants_count > 0)
    summaryParts.push(`${fmt(activation.generation.variants_count)} variants`);
  if (activation?.generation?.eval_pairs_count != null && activation.generation.eval_pairs_count > 0)
    summaryParts.push(`${fmt(activation.generation.eval_pairs_count)} eval pairs`);

  const showButtons = activation?.analysis != null;

  return (
    <section
      style={{ fontFamily: "monospace" }}
      className="mt-8 rounded-lg border border-neutral-200 p-6 dark:border-neutral-800"
    >
      <h2 className="mb-3 text-lg font-semibold">Verum Integration</h2>

      {/* Summary row */}
      <p className="mb-5 text-sm text-neutral-500 dark:text-neutral-400">
        {summaryParts.length > 0 ? summaryParts.join(" · ") : "Analysis in progress…"}
      </p>

      {showButtons && (
        <div className="flex flex-col gap-4 sm:flex-row sm:gap-6">
          {/* Phase 0 — Observe */}
          <PrButton
            label="Phase 0 — Observe only"
            description="Adds OTLP env vars to .env.example. Zero code changes."
            buttonLabel="Add OTLP env vars"
            state={observeState}
            onReset={() => setObserveState("idle")}
            onClick={() => void handlePr("observe")}
          />

          {/* Phase 1 — Auto-instrument */}
          <PrButton
            label="Phase 1 — Auto-instrument"
            description="Adds `import verum.openai` near your LLM imports. 1-line change."
            buttonLabel="Add auto-instrument"
            state={bidirectionalState}
            onReset={() => setBidirectionalState("idle")}
            onClick={() => void handlePr("bidirectional")}
          />
        </div>
      )}
    </section>
  );
}

interface PrButtonProps {
  readonly label: string;
  readonly description: string;
  readonly buttonLabel: string;
  readonly state: ButtonState;
  readonly onReset: () => void;
  readonly onClick: () => void;
}

function PrButton({ label, description, buttonLabel, state, onReset, onClick }: PrButtonProps) {
  return (
    <div className="flex flex-1 flex-col gap-2">
      <p className="text-xs font-medium text-neutral-700 dark:text-neutral-300">{label}</p>
      <p className="text-xs text-neutral-400 dark:text-neutral-500">{description}</p>

      {state === "idle" && (
        <button
          onClick={onClick}
          className="mt-1 w-fit rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
        >
          {buttonLabel}
        </button>
      )}

      {state === "loading" && (
        <div role="status" className="mt-1 flex items-center gap-2 text-xs text-neutral-500">
          <span
            aria-label="loading"
            className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-blue-500 border-t-transparent"
          />
          Creating PR on GitHub…
        </div>
      )}

      {typeof state === "object" && "alreadyDone" in state && (
        <div className="mt-1 rounded-md bg-slate-50 px-3 py-2 border border-slate-200">
          <p className="text-xs text-slate-600">Already up to date — Verum config already present in repo.</p>
        </div>
      )}

      {typeof state === "object" && "prUrl" in state && (
        <div className="mt-1 rounded-md bg-green-50 px-3 py-2 dark:bg-green-950">
          <p className="text-xs font-medium text-green-800 dark:text-green-200">
            PR #{state.prNumber} opened
          </p>
          <a
            href={state.prUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-0.5 inline-block text-xs text-blue-600 underline hover:text-blue-800 dark:text-blue-400"
          >
            View on GitHub →
          </a>
        </div>
      )}

      {typeof state === "object" && "error" in state && (
        <div className="mt-1 rounded-md bg-red-50 px-3 py-2 dark:bg-red-950">
          <p className="text-xs text-red-800 dark:text-red-200">Failed: {state.error}</p>
          <button
            onClick={onReset}
            className="mt-1 text-xs text-red-600 underline hover:text-red-800 dark:text-red-400"
          >
            Try again
          </button>
        </div>
      )}
    </div>
  );
}
