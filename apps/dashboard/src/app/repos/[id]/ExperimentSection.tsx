"use client";

import { useCallback, useEffect, useState } from "react";
import { useAdaptivePolling } from "@/hooks/useAdaptivePolling";
import { t } from "@/lib/i18n";

interface Experiment {
  id: string;
  baseline_variant: string;
  challenger_variant: string;
  status: string;
  winner_variant: string | null;
  confidence: number | null;
  baseline_wins: number;
  baseline_n: number;
  challenger_wins: number;
  challenger_n: number;
  started_at: string;
  converged_at: string | null;
}

interface ExperimentsResponse {
  experiments: Experiment[];
  current_experiment: Experiment | null;
}

interface Props {
  deploymentId: string;
}

const CHALLENGER_ORDER = ["cot", "few_shot", "role_play", "concise"];

export default function ExperimentSection({ deploymentId }: Props) {
  const [data, setData] = useState<ExperimentsResponse | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const r = await fetch(`/api/v1/experiments?deployment_id=${deploymentId}`, {
        cache: "no-store",
      });
      if (r.ok) {
        setData(await r.json() as ExperimentsResponse);
      }
    } catch {
      // ignore network errors during polling
    }
  }, [deploymentId]);

  // Kick off an immediate fetch on mount, independently of the polling callback.
  // Using inline fetch instead of fetchData to avoid set-state-in-effect lint rule.
  useEffect(() => {
    let cancelled = false;
    fetch(`/api/v1/experiments?deployment_id=${deploymentId}`, { cache: "no-store" })
      .then(async (r) => {
        if (r.ok && !cancelled) setData(await r.json() as ExperimentsResponse);
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [deploymentId]);

  const experimentActive = data?.current_experiment != null;
  useAdaptivePolling(fetchData, experimentActive, {
    minIntervalMs: 3_000,
    maxIntervalMs: 30_000,
    backoffFactor: 2,
  });

  if (!data) {
    return (
      <div style={{ borderLeft: "3px solid #7c3aed", paddingLeft: 16, marginBottom: 32 }}>
        <h2 style={{ fontSize: 15, color: "#7c3aed", margin: "0 0 12px" }}>[7] EXPERIMENT</h2>
        <p style={{ color: "#888", fontSize: 13 }}>{t("trace", "loading")}</p>
      </div>
    );
  }

  const { experiments: allExps, current_experiment: current } = data;
  const converged = allExps.filter((e) => e.status === "converged");

  return (
    <div style={{ borderLeft: "3px solid #7c3aed", paddingLeft: 16, marginBottom: 32 }}>
      <h2 style={{ fontSize: 15, color: "#7c3aed", margin: "0 0 12px" }}>[7] EXPERIMENT</h2>

      {/* Current running experiment */}
      {current && (
        <div style={{ marginBottom: 16 }}>
          <p style={{ fontSize: 13, color: "#aaa", marginBottom: 8 }}>
            {`Running — round ${CHALLENGER_ORDER.indexOf(current.challenger_variant) + 1}/4: `}
            <strong>{current.baseline_variant}</strong> vs{" "}
            <strong style={{ color: "#a78bfa" }}>{current.challenger_variant}</strong>
          </p>

          {/* Stats row */}
          <div style={{ display: "flex", gap: 12, marginBottom: 12 }}>
            <VariantCard
              label="Baseline"
              variant={current.baseline_variant}
              wins={current.baseline_wins}
              n={current.baseline_n}
            />
            <VariantCard
              label="Challenger"
              variant={current.challenger_variant}
              wins={current.challenger_wins}
              n={current.challenger_n}
              highlight
            />
          </div>

          {/* Confidence bar */}
          {current.confidence != null && (
            <ConfidenceBar confidence={current.confidence} />
          )}
        </div>
      )}

      {/* History */}
      {converged.length > 0 && (
        <div>
          <p style={{ fontSize: 12, color: "#666", marginBottom: 6 }}>History</p>
          <div style={{ border: "1px solid #222", borderRadius: 6, overflow: "hidden" }}>
            {converged.map((e, i) => (
              <div
                key={e.id}
                style={{
                  display: "grid",
                  gridTemplateColumns: "40px 1fr 1fr 1fr 80px",
                  gap: 8,
                  padding: "8px 12px",
                  fontSize: 12,
                  borderBottom: "1px solid #111",
                  color: "#ccc",
                }}
              >
                <span style={{ color: "#666" }}>{i + 1}/4</span>
                <span style={{ fontFamily: "monospace" }}>{e.baseline_variant}</span>
                <span style={{ fontFamily: "monospace", color: "#a78bfa" }}>{e.challenger_variant}</span>
                <span style={{ color: e.winner_variant === e.challenger_variant ? "#4ade80" : "#888" }}>
                  {e.winner_variant ?? "—"}
                </span>
                <span>{e.confidence != null ? `${(e.confidence * 100).toFixed(1)}%` : "—"}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* All done */}
      {!current && allExps.length > 0 && allExps[0]?.status === "converged" && (
        <p style={{ fontSize: 13, color: "#4ade80", marginTop: 8 }}>
          Done — winner:{" "}
          <strong style={{ fontFamily: "monospace" }}>{allExps[0].winner_variant}</strong>
        </p>
      )}
    </div>
  );
}

function VariantCard({
  label,
  variant,
  wins,
  n,
  highlight = false,
}: {
  label: string;
  variant: string;
  wins: number;
  n: number;
  highlight?: boolean;
}) {
  return (
    <div
      style={{
        flex: 1,
        border: `1px solid ${highlight ? "#7c3aed" : "#333"}`,
        borderRadius: 6,
        padding: "10px 12px",
        background: "#0a0a0a",
      }}
    >
      <div style={{ fontSize: 11, color: "#666", marginBottom: 4 }}>{label}</div>
      <div style={{ fontFamily: "monospace", fontSize: 13, color: highlight ? "#a78bfa" : "#ccc", fontWeight: "bold" }}>
        {variant}
      </div>
      <div style={{ fontSize: 11, color: "#888", marginTop: 6 }}>
        Traces: {n} / 100
      </div>
      <div style={{ fontSize: 11, color: "#aaa" }}>
        Win rate: {n > 0 ? ((wins / n) * 100).toFixed(1) : "0.0"}%
      </div>
    </div>
  );
}

function ConfidenceBar({ confidence }: { confidence: number }) {
  const pct = Math.round(confidence * 100);
  const color = pct >= 95 ? "#4ade80" : pct <= 5 ? "#f87171" : "#a78bfa";
  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "#666", marginBottom: 4 }}>
        <span>P(Challenger &gt; Baseline)</span>
        <span style={{ color }}>{pct}%</span>
      </div>
      <div style={{ background: "#222", borderRadius: 4, height: 6, overflow: "hidden", position: "relative" }}>
        <div style={{ width: `${pct}%`, height: "100%", background: color, transition: "width 0.5s" }} />
        {/* threshold markers at 5% and 95% */}
        <div style={{ position: "absolute", top: 0, left: "5%", width: 1, height: "100%", background: "#facc15", opacity: 0.5 }} />
        <div style={{ position: "absolute", top: 0, left: "95%", width: 1, height: "100%", background: "#facc15", opacity: 0.5 }} />
      </div>
    </div>
  );
}
