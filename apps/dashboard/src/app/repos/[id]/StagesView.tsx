"use client";

import { useState, useCallback } from "react";
import type { RepoStatus } from "@/lib/db/queries";
import { useAdaptivePolling } from "@/hooks/useAdaptivePolling";
import { rerunAnalyze, rerunInfer, rerunHarvest, rerunGenerate } from "./actions";
import ObserveSection from "./ObserveSection";
import ExperimentSection from "./ExperimentSection";

interface Props {
  initial: RepoStatus;
  repoId: string;
  workerAlive: boolean;
}

// Stage metadata for the stepper
const STAGES = [
  { key: "analyze", label: "ANALYZE" },
  { key: "infer", label: "INFER" },
  { key: "harvest", label: "HARVEST" },
  { key: "generate", label: "GENERATE" },
  { key: "deploy", label: "DEPLOY" },
  { key: "observe", label: "OBSERVE" },
  { key: "experiment", label: "EXPERIMENT" },
  { key: "evolve", label: "EVOLVE" },
] as const;

const STAGE_COLORS: Record<string, { dot: string; bg: string; text: string; leftBorder: string; progress: string }> = {
  analyze:    { dot: "bg-green-500",   bg: "bg-green-50",   text: "text-green-700",   leftBorder: "border-l-green-400",   progress: "bg-gradient-to-r from-green-400 to-green-500" },
  infer:      { dot: "bg-violet-500",  bg: "bg-violet-50",  text: "text-violet-700",  leftBorder: "border-l-violet-400",  progress: "bg-gradient-to-r from-violet-400 to-violet-500" },
  harvest:    { dot: "bg-amber-500",   bg: "bg-amber-50",   text: "text-amber-700",   leftBorder: "border-l-amber-400",   progress: "bg-gradient-to-r from-amber-400 to-amber-500" },
  generate:   { dot: "bg-red-500",     bg: "bg-red-50",     text: "text-red-700",     leftBorder: "border-l-red-400",     progress: "bg-gradient-to-r from-red-400 to-red-500" },
  deploy:     { dot: "bg-blue-500",    bg: "bg-blue-50",    text: "text-blue-700",    leftBorder: "border-l-blue-400",    progress: "bg-gradient-to-r from-blue-400 to-blue-500" },
  observe:    { dot: "bg-emerald-500", bg: "bg-emerald-50", text: "text-emerald-700", leftBorder: "border-l-emerald-400", progress: "bg-gradient-to-r from-emerald-400 to-emerald-500" },
  experiment: { dot: "bg-fuchsia-500", bg: "bg-fuchsia-50", text: "text-fuchsia-700", leftBorder: "border-l-fuchsia-400", progress: "bg-gradient-to-r from-fuchsia-400 to-fuchsia-500" },
  evolve:     { dot: "bg-teal-500",    bg: "bg-teal-50",    text: "text-teal-700",    leftBorder: "border-l-teal-400",    progress: "bg-gradient-to-r from-teal-400 to-teal-500" },
};

export default function StagesView({ initial, repoId, workerAlive: _workerAlive }: Props) {
  const [status, setStatus] = useState<RepoStatus>(initial);

  const {
    repo,
    latestAnalysis,
    latestInference,
    harvestChunks,
    harvestSourcesDone,
    harvestSourcesTotal,
    latestGeneration,
    latestDeploymentId,
    latestDeploymentExperimentStatus,
  } = status;

  const isRunning = (s: string | null | undefined) => s === "pending" || s === "running";

  const anyJobActive =
    isRunning(latestAnalysis?.status) ||
    isRunning(latestInference?.status) ||
    isRunning(latestGeneration?.status);

  const pollStatus = useCallback(async () => {
    const ac = new AbortController();
    try {
      const r = await fetch(`/api/repos/${repoId}/status`, {
        signal: ac.signal,
        cache: "no-store",
      });
      if (r.ok) {
        const json = (await r.json()) as { status: RepoStatus; workerAlive: boolean };
        setStatus(json.status);
      }
    } catch {
      // ignore AbortError and network errors
    }
  }, [repoId]);

  useAdaptivePolling(pollStatus, anyJobActive, {
    minIntervalMs: 2_000,
    maxIntervalMs: 30_000,
    backoffFactor: 2,
  });

  // Derive stage completion states for the stepper
  const analyzeStatus = latestAnalysis?.status ?? null;
  const inferStatus = latestInference?.status ?? null;
  const harvestDone = harvestChunks > 0 && harvestSourcesDone >= harvestSourcesTotal && harvestSourcesTotal > 0;
  const harvestRunning = !harvestDone && (harvestChunks > 0 || harvestSourcesTotal > 0);
  const generateStatus = latestGeneration?.status ?? null;
  const deployDone = !!latestDeploymentId;

  type StepState = "done" | "active" | "pending";
  const stepStates: StepState[] = [
    analyzeStatus === "done" ? "done" : isRunning(analyzeStatus) ? "active" : "pending",
    inferStatus === "done" ? "done" : isRunning(inferStatus) ? "active" : "pending",
    harvestDone ? "done" : harvestRunning ? "active" : "pending",
    generateStatus === "done" ? "done" : isRunning(generateStatus) ? "active" : "pending",
    deployDone ? "done" : "pending",
    deployDone ? "done" : "pending",
    latestDeploymentExperimentStatus && latestDeploymentExperimentStatus !== "idle" ? "done" : "pending",
    "pending",
  ];

  // Active stage key for the active stage card
  const activeStageIdx = stepStates.findIndex((s) => s === "active");
  const activeStageKey = activeStageIdx >= 0 ? STAGES[activeStageIdx].key : null;
  const activeColors = activeStageKey ? STAGE_COLORS[activeStageKey] : null;

  // Quick stats
  const callSitesCount = Array.isArray(latestAnalysis?.call_sites)
    ? (latestAnalysis.call_sites as unknown[]).length
    : null;

  return (
    <div className="space-y-4">
      {/* ── Loop Progress Stepper ── */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <p className="mb-4 text-xs font-semibold uppercase tracking-wide text-slate-400">
          Verum Loop Progress
        </p>
        <div className="flex items-center">
          {STAGES.map((stage, i) => {
            const state = stepStates[i];
            const colors = STAGE_COLORS[stage.key];
            const isLast = i === STAGES.length - 1;
            return (
              <div key={stage.key} className="flex flex-1 items-center">
                <div className="flex flex-col items-center gap-1.5">
                  {state === "done" ? (
                    <div className={`flex h-7 w-7 items-center justify-center rounded-full ${colors.dot}`}>
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3">
                        <polyline points="20 6 9 17 4 12" />
                      </svg>
                    </div>
                  ) : state === "active" ? (
                    <div className={`flex h-7 w-7 items-center justify-center rounded-full border-2 ${colors.dot.replace("bg-", "border-")} ${colors.bg}`}>
                      <span className={`h-2 w-2 animate-pulse rounded-full ${colors.dot}`} />
                    </div>
                  ) : (
                    <div className="flex h-7 w-7 items-center justify-center rounded-full border-2 border-slate-200 bg-slate-50">
                      <span className="text-[9px] font-bold text-slate-300">{i + 1}</span>
                    </div>
                  )}
                  <span
                    className={`text-center text-[9px] font-semibold leading-tight ${
                      state === "done"
                        ? colors.text
                        : state === "active"
                          ? colors.text
                          : "text-slate-300"
                    }`}
                    style={{ width: "40px" }}
                  >
                    {stage.label}
                  </span>
                </div>
                {!isLast && (
                  <div
                    className={`mb-5 h-0.5 flex-1 ${
                      stepStates[i] === "done" ? colors.dot.replace("bg-", "bg-") : "bg-slate-200"
                    }`}
                  />
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* ── Active Stage Card ── */}
      {activeStageKey && activeColors && (
        <div className={`rounded-xl border border-slate-200 border-l-4 ${activeColors.leftBorder} ${activeColors.bg} p-4`}>
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className={`rounded-full px-2 py-0.5 text-xs font-bold ${activeColors.bg} ${activeColors.text}`}>
                {STAGES[activeStageIdx].label}
              </span>
              <span className={`flex items-center gap-1.5 text-xs ${activeColors.text}`}>
                <span className={`inline-block h-1.5 w-1.5 animate-pulse rounded-full ${activeColors.dot}`} />
                Running
              </span>
            </div>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/50">
            <div className={`h-full w-1/3 rounded-full ${activeColors.progress}`} />
          </div>
        </div>
      )}

      {/* ── Quick Stats ── */}
      {(callSitesCount !== null || latestInference?.domain || harvestChunks > 0) && (
        <div className="grid grid-cols-3 gap-3">
          {callSitesCount !== null && (
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="mb-1 text-xs text-slate-400">Call Sites</p>
              <p className="text-xl font-bold text-slate-900">{callSitesCount}</p>
              <p className="mt-0.5 font-mono text-xs text-slate-500">
                {latestAnalysis?.call_sites != null &&
                  [...new Set(
                    (latestAnalysis.call_sites as Array<Record<string, unknown>>)
                      .map((c) => (typeof c.sdk === "string" ? c.sdk : null))
                      .filter((s): s is string => s !== null)
                  )].join(" · ")}
              </p>
            </div>
          )}
          {latestInference?.domain && (
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="mb-1 text-xs text-slate-400">Domain</p>
              <p className="text-sm font-bold text-violet-600">{latestInference.domain}</p>
              {latestInference.confidence != null && (
                <p className="mt-0.5 text-xs text-slate-500">
                  conf. {latestInference.confidence.toFixed(2)}
                </p>
              )}
            </div>
          )}
          {harvestChunks > 0 && (
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="mb-1 text-xs text-slate-400">Chunks</p>
              <p className="text-xl font-bold text-slate-900">{harvestChunks.toLocaleString()}</p>
              <p className="mt-0.5 text-xs text-slate-500">
                {harvestSourcesDone}/{harvestSourcesTotal} sources
              </p>
            </div>
          )}
        </div>
      )}

      {/* ── Stage Detail Sections ── */}
      <div className="space-y-3">
        <StageSection title="[1] ANALYZE" colorClass="border-l-green-400">
          {latestAnalysis ? (
            <div>
              <StageRow label="Status" value={isRunning(latestAnalysis.status) ? `${latestAnalysis.status} (running...)` : latestAnalysis.status} />
              {latestAnalysis.call_sites != null && (
                <StageRow label="Call sites" value={String((latestAnalysis.call_sites as unknown[]).length)} />
              )}
              {latestAnalysis.analyzed_at && (
                <StageRow label="Analyzed" value={new Date(latestAnalysis.analyzed_at).toLocaleString()} />
              )}
              {latestAnalysis.status === "done" && (
                <a href={`/analyses/${latestAnalysis.id}`} className="mt-2 inline-block text-xs text-green-600 hover:underline">
                  View full analysis →
                </a>
              )}
            </div>
          ) : (
            <p className="text-xs text-slate-400">No analysis yet.</p>
          )}
          <form action={rerunAnalyze.bind(null, repo.id, repo.github_url, repo.default_branch)} className="mt-3">
            <button type="submit" className="rounded-md bg-green-500 px-3 py-1.5 text-xs font-semibold text-white hover:bg-green-600 transition-colors">
              {latestAnalysis ? "Re-run ANALYZE" : "Run ANALYZE"}
            </button>
          </form>
        </StageSection>

        <StageSection title="[2] INFER" colorClass="border-l-violet-400">
          {latestInference ? (
            <div>
              <StageRow label="Status" value={isRunning(latestInference.status) ? `${latestInference.status} (running...)` : latestInference.status} />
              {latestInference.domain && <StageRow label="Domain" value={latestInference.domain} />}
              {latestInference.confidence != null && (
                <StageRow label="Confidence" value={`${(latestInference.confidence * 100).toFixed(0)}%`} />
              )}
              {latestInference.status === "done" && latestInference.domain && (
                <div className="mt-3 rounded-lg bg-violet-50 border border-violet-200 p-3">
                  <p className="text-xs font-semibold text-violet-700 mb-1">
                    Verum understood your service as:
                  </p>
                  <p className="text-sm font-bold text-violet-900">{latestInference.domain}</p>
                  {latestInference.confidence != null && (
                    <p className="text-xs text-violet-500 mt-0.5">
                      {(latestInference.confidence * 100).toFixed(0)}% confidence
                    </p>
                  )}
                  <p className="mt-2 text-xs text-violet-600">
                    Knowledge harvesting started automatically. If this is wrong, re-run INFER.
                  </p>
                </div>
              )}
              {latestInference.status === "done" && (
                <a href={`/infer/${latestAnalysis?.id}?inference_id=${latestInference.id}`} className="mt-2 inline-block text-xs text-violet-600 hover:underline">
                  View full INFER details →
                </a>
              )}
            </div>
          ) : (
            <p className="text-xs text-slate-400">
              {latestAnalysis?.status === "done" ? "Analysis complete — ready to infer." : "Run ANALYZE first."}
            </p>
          )}
          {latestAnalysis?.status === "done" && (
            <form action={rerunInfer.bind(null, repo.id, latestAnalysis.id)} className="mt-3">
              <button type="submit" className="rounded-md bg-violet-500 px-3 py-1.5 text-xs font-semibold text-white hover:bg-violet-600 transition-colors">
                {latestInference ? "Re-run INFER" : "Run INFER"}
              </button>
            </form>
          )}
        </StageSection>

        <StageSection title="[3] HARVEST" colorClass="border-l-amber-400">
          {harvestChunks > 0 ? (
            <div>
              <StageRow label="Sources" value={`${harvestSourcesDone} done / ${harvestSourcesTotal} total`} />
              <StageRow label="Chunks" value={harvestChunks.toLocaleString()} />
              {latestInference && (
                <div className="mt-2 flex gap-4">
                  <a href={`/harvest/${latestInference.id}`} className="text-xs text-amber-600 hover:underline">View harvest status →</a>
                  <a href={`/retrieve?inference_id=${latestInference.id}`} className="text-xs text-amber-600 hover:underline">Search knowledge →</a>
                </div>
              )}
            </div>
          ) : (
            <p className="text-xs text-slate-400">
              {latestInference?.status === "done"
                ? "Knowledge sources identified — crawling in progress."
                : "Run INFER first."}
            </p>
          )}
          {latestInference?.status === "done" && latestAnalysis && (
            <form action={rerunHarvest.bind(null, latestInference.id, latestAnalysis.id)} className="mt-3">
              <button type="submit" className="rounded-md bg-amber-500 px-3 py-1.5 text-xs font-semibold text-white hover:bg-amber-600 transition-colors">
                {harvestChunks > 0 ? "Re-trigger HARVEST" : "Run HARVEST"}
              </button>
            </form>
          )}
        </StageSection>

        <StageSection title="[4] GENERATE" colorClass="border-l-red-400">
          {latestGeneration ? (
            <div>
              <StageRow label="Status" value={isRunning(latestGeneration.status) ? `${latestGeneration.status} (running...)` : latestGeneration.status} />
              {latestGeneration.status === "done" && (
                <>
                  <StageRow label="Prompt variants" value={String(latestGeneration.variant_count)} />
                  <StageRow label="Eval pairs" value={String(latestGeneration.eval_count)} />
                </>
              )}
            </div>
          ) : (
            <p className="text-xs text-slate-400">
              {harvestChunks > 0 ? "Generate in progress or not started." : "Complete HARVEST first."}
            </p>
          )}
          {latestInference?.status === "done" && harvestChunks > 0 && (
            <form action={rerunGenerate.bind(null, latestInference.id)} className="mt-3">
              <button type="submit" className="rounded-md bg-red-500 px-3 py-1.5 text-xs font-semibold text-white hover:bg-red-600 transition-colors">
                {latestGeneration ? "Re-run GENERATE" : "Run GENERATE"}
              </button>
            </form>
          )}
        </StageSection>

        <StageSection title="[5] RETRIEVE" colorClass="border-l-blue-400">
          {latestInference?.status === "done" && harvestChunks > 0 ? (
            <div>
              <StageRow label="Chunks available" value={harvestChunks.toLocaleString()} />
              <a href={`/retrieve?inference_id=${latestInference.id}`} className="mt-2 inline-block text-xs text-blue-600 hover:underline">
                Search knowledge →
              </a>
            </div>
          ) : (
            <p className="text-xs text-slate-400">Complete HARVEST first.</p>
          )}
        </StageSection>

        {latestDeploymentId && (
          <ObserveSection deploymentId={latestDeploymentId} />
        )}

        {latestDeploymentId &&
          latestDeploymentExperimentStatus &&
          latestDeploymentExperimentStatus !== "idle" && (
            <ExperimentSection deploymentId={latestDeploymentId} />
          )}
      </div>
    </div>
  );
}

function StageSection({
  title,
  colorClass,
  children,
}: {
  title: string;
  colorClass: string;
  children: React.ReactNode;
}) {
  return (
    <div className={`rounded-xl border-l-4 border border-slate-200 bg-white p-4 shadow-sm ${colorClass}`}>
      <h2 className="mb-3 text-xs font-bold uppercase tracking-wide text-slate-500">{title}</h2>
      {children}
    </div>
  );
}

function StageRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-3 text-xs text-slate-600 mb-1">
      <span className="w-24 flex-shrink-0 text-slate-400">{label}</span>
      <span className="font-medium">{value}</span>
    </div>
  );
}
