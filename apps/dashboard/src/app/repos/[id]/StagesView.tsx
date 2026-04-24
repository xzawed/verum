"use client";

import { useState, useEffect, useCallback } from "react";
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

export default function StagesView({ initial, repoId, workerAlive: initialWorkerAlive }: Props) {
  const [status, setStatus] = useState<RepoStatus>(initial);
  const [alive, setAlive] = useState(initialWorkerAlive);

  const { repo, latestAnalysis, latestInference, harvestChunks, harvestSourcesDone, harvestSourcesTotal, latestGeneration, latestDeploymentId, latestDeploymentExperimentStatus } = status;
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
        const json = await r.json() as { status: RepoStatus; workerAlive: boolean };
        setStatus(json.status);
        setAlive(json.workerAlive);
      }
    } catch {
      // ignore AbortError and network errors during polling
    }
  }, [repoId]);

  useAdaptivePolling(pollStatus, anyJobActive, {
    minIntervalMs: 2_000,
    maxIntervalMs: 30_000,
    backoffFactor: 2,
  });

  return (
    <>
      {/* Worker status badge */}
      <div style={{ marginBottom: 8, fontSize: 11, color: alive ? "#059669" : "#dc2626" }}>
        ● worker {alive ? "online" : "offline"}
      </div>

      {/* ── ANALYZE ── */}
      <Section title="[1] ANALYZE" color="#0066cc">
        {latestAnalysis ? (
          <div>
            <StatusRow
              label="Status"
              value={isRunning(latestAnalysis.status) ? `${latestAnalysis.status} (running...)` : latestAnalysis.status}
            />
            {latestAnalysis.call_sites != null && (
              <StatusRow label="Call sites" value={String((latestAnalysis.call_sites as unknown[]).length)} />
            )}
            {latestAnalysis.analyzed_at && (
              <StatusRow label="Analyzed" value={new Date(latestAnalysis.analyzed_at).toLocaleString()} />
            )}
            {latestAnalysis.status === "done" && (
              <a href={`/analyses/${latestAnalysis.id}`} style={{ display: "inline-block", marginTop: 8, fontSize: 12, color: "#0066cc" }}>
                View full analysis →
              </a>
            )}
          </div>
        ) : (
          <p style={{ color: "#888", fontSize: 13 }}>No analysis yet.</p>
        )}
        <form action={rerunAnalyze.bind(null, repo.id, repo.github_url, repo.default_branch)} style={{ marginTop: 12 }}>
          <button type="submit" style={btnStyle}>
            {latestAnalysis ? "Re-run ANALYZE" : "Run ANALYZE"}
          </button>
        </form>
      </Section>

      {/* ── INFER ── */}
      <Section title="[2] INFER" color="#7c3aed">
        {latestInference ? (
          <div>
            <StatusRow
              label="Status"
              value={isRunning(latestInference.status) ? `${latestInference.status} (running...)` : latestInference.status}
            />
            {latestInference.domain && <StatusRow label="Domain" value={latestInference.domain} />}
            {latestInference.confidence != null && (
              <StatusRow label="Confidence" value={`${(latestInference.confidence * 100).toFixed(0)}%`} />
            )}
            {latestInference.status === "done" && (
              <a
                href={`/infer/${latestAnalysis?.id}?inference_id=${latestInference.id}`}
                style={{ display: "inline-block", marginTop: 8, fontSize: 12, color: "#7c3aed" }}
              >
                View inference + approve sources →
              </a>
            )}
          </div>
        ) : (
          <p style={{ color: "#888", fontSize: 13 }}>
            {latestAnalysis?.status === "done" ? "Analysis complete — ready to infer." : "Run ANALYZE first."}
          </p>
        )}
        {latestAnalysis?.status === "done" && (
          <form action={rerunInfer.bind(null, repo.id, latestAnalysis.id)} style={{ marginTop: 12 }}>
            <button type="submit" style={{ ...btnStyle, background: "#7c3aed" }}>
              {latestInference ? "Re-run INFER" : "Run INFER"}
            </button>
          </form>
        )}
      </Section>

      {/* ── HARVEST ── */}
      <Section title="[3] HARVEST" color="#059669">
        {harvestChunks > 0 ? (
          <div>
            <StatusRow label="Sources" value={`${harvestSourcesDone} done / ${harvestSourcesTotal} total`} />
            <StatusRow label="Chunks" value={harvestChunks.toLocaleString()} />
            {latestInference && (
              <div style={{ marginTop: 8, display: "flex", gap: 12 }}>
                <a href={`/harvest/${latestInference.id}`} style={{ fontSize: 12, color: "#059669" }}>View harvest status →</a>
                <a href={`/retrieve?inference_id=${latestInference.id}`} style={{ fontSize: 12, color: "#059669" }}>Search knowledge →</a>
              </div>
            )}
          </div>
        ) : (
          <p style={{ color: "#888", fontSize: 13 }}>
            {latestInference?.status === "done" ? "Harvest in progress or no sources." : "Run INFER first."}
          </p>
        )}
        {latestInference?.status === "done" && latestAnalysis && (
          <form action={rerunHarvest.bind(null, latestInference.id, latestAnalysis.id)} style={{ marginTop: 12 }}>
            <button type="submit" style={{ ...btnStyle, background: "#059669" }}>
              {harvestChunks > 0 ? "Re-trigger HARVEST" : "Run HARVEST"}
            </button>
          </form>
        )}
      </Section>

      {/* ── GENERATE ── */}
      <Section title="[4] GENERATE" color="#dc2626">
        {latestGeneration ? (
          <div>
            <StatusRow
              label="Status"
              value={isRunning(latestGeneration.status) ? `${latestGeneration.status} (running...)` : latestGeneration.status}
            />
            {latestGeneration.status === "done" && (
              <>
                <StatusRow label="Prompt variants" value={String(latestGeneration.variant_count)} />
                <StatusRow label="Eval pairs" value={String(latestGeneration.eval_count)} />
              </>
            )}
          </div>
        ) : (
          <p style={{ color: "#888", fontSize: 13 }}>
            {harvestChunks > 0 ? "Generate in progress or not started." : "Complete HARVEST first."}
          </p>
        )}
        {latestInference?.status === "done" && harvestChunks > 0 && (
          <form action={rerunGenerate.bind(null, latestInference.id)} style={{ marginTop: 12 }}>
            <button type="submit" style={{ ...btnStyle, background: "#dc2626" }}>
              {latestGeneration ? "Re-run GENERATE" : "Run GENERATE"}
            </button>
          </form>
        )}
      </Section>

      {/* ── RETRIEVE ── */}
      <Section title="[5] RETRIEVE" color="#b45309">
        {latestInference?.status === "done" && harvestChunks > 0 ? (
          <div>
            <StatusRow label="Chunks available" value={harvestChunks.toLocaleString()} />
            <a
              href={`/retrieve?inference_id=${latestInference.id}`}
              style={{ display: "inline-block", marginTop: 8, fontSize: 12, color: "#b45309" }}
            >
              Search knowledge →
            </a>
          </div>
        ) : (
          <p style={{ color: "#888", fontSize: 13 }}>Complete HARVEST first.</p>
        )}
      </Section>

      {/* OBSERVE: visible when a deployment exists */}
      {latestDeploymentId && (
        <ObserveSection deploymentId={latestDeploymentId} />
      )}

      {/* EXPERIMENT: visible when experiment is running or completed */}
      {latestDeploymentId && latestDeploymentExperimentStatus && latestDeploymentExperimentStatus !== "idle" && (
        <ExperimentSection deploymentId={latestDeploymentId} />
      )}
    </>
  );
}

function Section({ title, color, children }: { title: string; color: string; children: React.ReactNode }) {
  return (
    <div style={{ borderLeft: `3px solid ${color}`, paddingLeft: 16, marginBottom: 32 }}>
      <h2 style={{ fontSize: 15, color, margin: "0 0 12px" }}>{title}</h2>
      {children}
    </div>
  );
}

function StatusRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", gap: 12, fontSize: 13, marginBottom: 4 }}>
      <span style={{ color: "#666", width: 100, flexShrink: 0 }}>{label}</span>
      <span>{value}</span>
    </div>
  );
}

const btnStyle: React.CSSProperties = {
  padding: "7px 16px",
  fontSize: 12,
  fontWeight: "bold",
  background: "#0066cc",
  color: "white",
  border: "none",
  cursor: "pointer",
};
