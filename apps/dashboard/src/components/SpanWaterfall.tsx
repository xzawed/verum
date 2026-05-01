"use client";

import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import { useLocale } from "@/context/LocaleContext";
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
  const { locale } = useLocale();

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
      <motion.button
        type="button"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.2 }}
        className="fixed inset-0 bg-black/50 z-40 cursor-default border-0 p-0"
        aria-label="Close panel"
        onClick={onClose}
      />

      {/* Panel */}
      <motion.div
        initial={{ x: "100%" }}
        animate={{ x: 0 }}
        transition={{ type: "spring", stiffness: 350, damping: 35 }}
        className="fixed right-0 top-0 h-full w-96 bg-gray-950 border-l border-gray-800 z-50 overflow-y-auto"
      >
        <div className="flex items-center justify-between p-4 border-b border-gray-800">
          <h3 className="text-sm font-semibold text-white">{t("trace", "panelTitle", locale)}</h3>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-white text-lg leading-none"
          >
            ×
          </button>
        </div>

        {loading ? (
          <div className="p-4 text-xs text-gray-500">{t("trace", "loading", locale)}</div>
        ) : detail == null ? (
          <div className="p-4 text-xs text-red-400">{t("trace", "notFound", locale)}</div>
        ) : (
          <div className="p-4 space-y-4">
            {/* Metadata */}
            <Section title={t("trace", "sectionMeta", locale)}>
              <Row label={t("trace", "labelId", locale)} value={<span className="font-mono text-blue-400 text-xs">{detail.id}</span>} />
              <Row label={t("trace", "labelVariant", locale)} value={<span className="text-green-400">{detail.variant}</span>} />
              <Row
                label={t("trace", "labelFeedback", locale)}
                value={
                  detail.user_feedback === 1
                    ? t("trace", "feedbackPositive", locale)
                    : detail.user_feedback === -1
                    ? t("trace", "feedbackNegative", locale)
                    : t("trace", "feedbackNone", locale)
                }
              />
              <Row label={t("trace", "labelTimestamp", locale)} value={new Date(detail.created_at).toLocaleString()} />
            </Section>

            {/* Latency bar */}
            <Section title={t("trace", "sectionLatency", locale)}>
              <div className="bg-gray-900 rounded p-3">
                <div className="flex justify-between text-xs text-gray-400 mb-1">
                  <span>{detail.model}</span>
                  <span className="font-mono">{detail.latency_ms?.toLocaleString()}ms</span>
                </div>
                <div className="h-4 bg-gray-800 rounded overflow-hidden">
                  <motion.div
                    className="h-full bg-indigo-500 rounded"
                    initial={{ width: "0%" }}
                    animate={{ width: `${Math.min(100, (detail.latency_ms / 3000) * 100)}%` }}
                    transition={{ duration: 0.8, ease: "easeOut", delay: 0.2 }}
                  />
                </div>
              </div>
              {detail.error && (
                <p className="text-xs text-red-400 mt-2">{t("trace", "errorPrefix", locale)}{detail.error}</p>
              )}
            </Section>

            {/* Cost breakdown */}
            <Section title={t("trace", "sectionCost", locale)}>
              <Row label={t("trace", "labelInputTokens", locale)} value={detail.input_tokens?.toLocaleString()} />
              <Row label={t("trace", "labelOutputTokens", locale)} value={detail.output_tokens?.toLocaleString()} />
              <Row
                label={t("trace", "labelTotalCost", locale)}
                value={
                  <span className="text-green-400 font-mono">
                    ${Number(detail.cost_usd).toFixed(6)}
                  </span>
                }
              />
            </Section>

            {/* Judge score */}
            <Section title={t("trace", "sectionJudge", locale)}>
              {detail.judge_score != null ? (
                <>
                  <div className="flex items-center gap-2 mb-2">
                    <div className="flex-1 h-2 bg-gray-800 rounded overflow-hidden">
                      <motion.div
                        className={`h-full rounded ${
                          detail.judge_score >= 0.7 ? "bg-green-500" : "bg-yellow-500"
                        }`}
                        initial={{ width: "0%" }}
                        animate={{ width: `${detail.judge_score * 100}%` }}
                        transition={{ duration: 0.7, ease: "easeOut", delay: 0.3 }}
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
                      {t("trace", "judgedAt", locale)}{new Date(detail.judged_at).toLocaleString()}
                    </p>
                  )}
                </>
              ) : (
                <p className="text-xs text-gray-500 italic">{t("trace", "judgePending", locale)}</p>
              )}
            </Section>
          </div>
        )}
      </motion.div>
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
