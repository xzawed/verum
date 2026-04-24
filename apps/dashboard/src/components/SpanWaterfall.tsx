"use client";

import { useEffect, useState } from "react";
import { t } from "@/lib/i18n";

interface TraceDetail {
  id: string;
  variant: string;
  user_feedback: number | null;
  judge_score: number | null;
  created_at: string;
  latency_ms: number;
  cost_usd: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  error: string | null;
  judge_raw_response: string | null;
  judged_at: string | null;
}

interface Props {
  traceId: string;
  onClose: () => void;
}

export default function SpanWaterfall({ traceId, onClose }: Props) {
  const [detail, setDetail] = useState<TraceDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional pre-fetch reset, state update is not in render phase
    setLoading(true);
    fetch(`/api/v1/traces/${traceId}`)
      .then((r) => r.json())
      .then((data: unknown) => {
        setDetail(data as TraceDetail);
        setLoading(false);
      })
      .catch(/* istanbul ignore next */ () => {
        setLoading(false);
      });
  }, [traceId]);

  // Parse judge reason from raw_response JSON
  let judgeReason: string | null = null;
  if (detail?.judge_raw_response) {
    try {
      judgeReason = (JSON.parse(detail.judge_raw_response) as { reason?: string }).reason ?? null;
    } catch {
      judgeReason = null;
    }
  }

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 z-40"
        onClick={onClose}
      />

      {/* Panel */}
      <div className="fixed right-0 top-0 h-full w-96 bg-gray-950 border-l border-gray-800 z-50 overflow-y-auto">
        <div className="flex items-center justify-between p-4 border-b border-gray-800">
          <h3 className="text-sm font-semibold text-white">{t("trace", "panelTitle")}</h3>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-white text-lg leading-none"
          >
            ×
          </button>
        </div>

        {loading ? (
          <div className="p-4 text-xs text-gray-500">{t("trace", "loading")}</div>
        ) : detail == null ? (
          <div className="p-4 text-xs text-red-400">{t("trace", "notFound")}</div>
        ) : (
          <div className="p-4 space-y-4">
            {/* Metadata */}
            <Section title={t("trace", "sectionMeta")}>
              <Row label={t("trace", "labelId")} value={<span className="font-mono text-blue-400 text-xs">{detail.id}</span>} />
              <Row label={t("trace", "labelVariant")} value={<span className="text-green-400">{detail.variant}</span>} />
              <Row
                label={t("trace", "labelFeedback")}
                value={
                  detail.user_feedback === 1
                    ? t("trace", "feedbackPositive")
                    : detail.user_feedback === -1
                    ? t("trace", "feedbackNegative")
                    : t("trace", "feedbackNone")
                }
              />
              <Row label={t("trace", "labelTimestamp")} value={new Date(detail.created_at).toLocaleString()} />
            </Section>

            {/* Latency bar */}
            <Section title={t("trace", "sectionLatency")}>
              <div className="bg-gray-900 rounded p-3">
                <div className="flex justify-between text-xs text-gray-400 mb-1">
                  <span>{detail.model}</span>
                  <span className="font-mono">{detail.latency_ms?.toLocaleString()}ms</span>
                </div>
                <div className="h-4 bg-gray-800 rounded overflow-hidden">
                  <div
                    className="h-full bg-indigo-500 rounded"
                    style={{ width: `${Math.min(100, (detail.latency_ms / 3000) * 100)}%` }}
                  />
                </div>
              </div>
              {detail.error && (
                <p className="text-xs text-red-400 mt-2">{t("trace", "errorPrefix")}{detail.error}</p>
              )}
            </Section>

            {/* Cost breakdown */}
            <Section title={t("trace", "sectionCost")}>
              <Row label={t("trace", "labelInputTokens")} value={detail.input_tokens?.toLocaleString()} />
              <Row label={t("trace", "labelOutputTokens")} value={detail.output_tokens?.toLocaleString()} />
              <Row
                label={t("trace", "labelTotalCost")}
                value={
                  <span className="text-green-400 font-mono">
                    ${Number(detail.cost_usd).toFixed(6)}
                  </span>
                }
              />
            </Section>

            {/* Judge score */}
            <Section title={t("trace", "sectionJudge")}>
              {detail.judge_score != null ? (
                <>
                  <div className="flex items-center gap-2 mb-2">
                    <div className="flex-1 h-2 bg-gray-800 rounded overflow-hidden">
                      <div
                        className={`h-full rounded ${
                          detail.judge_score >= 0.7 ? "bg-green-500" : "bg-yellow-500"
                        }`}
                        style={{ width: `${detail.judge_score * 100}%` }}
                      />
                    </div>
                    <span className="text-sm font-bold text-white w-10 text-right">
                      {detail.judge_score.toFixed(2)}
                    </span>
                  </div>
                  {judgeReason && (
                    <p className="text-xs text-gray-400 bg-gray-900 rounded p-2">{judgeReason}</p>
                  )}
                  {detail.judged_at && (
                    <p className="text-xs text-gray-600 mt-1">
                      {t("trace", "judgedAt")}{new Date(detail.judged_at).toLocaleString()}
                    </p>
                  )}
                </>
              ) : (
                <p className="text-xs text-gray-500 italic">{t("trace", "judgePending")}</p>
              )}
            </Section>
          </div>
        )}
      </div>
    </>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">{title}</p>
      <div className="space-y-1">{children}</div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between text-xs">
      <span className="text-gray-500">{label}</span>
      <span className="text-gray-300">{value}</span>
    </div>
  );
}
