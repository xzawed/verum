"use client";

import { useEffect, useState } from "react";
import { t } from "@/lib/i18n";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import SpanWaterfall from "@/components/SpanWaterfall";

interface DailyMetric {
  date: string;
  total_cost_usd: number;
  call_count: number;
  p95_latency_ms: number;
  avg_judge_score: number | null;
}

interface TraceRow {
  id: string;
  variant: string;
  latency_ms: number;
  cost_usd: string;
  judge_score: number | null;
  user_feedback: number | null;
  created_at: string;
}

interface Props {
  deploymentId: string;
}

export default function ObserveSection({ deploymentId }: Props) {
  const [daily, setDaily] = useState<DailyMetric[]>([]);
  const [traces, setTraces] = useState<TraceRow[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [days, setDays] = useState(7);
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional pre-fetch reset, state update is not in render phase
    setLoading(true);
    Promise.all([
      fetch(`/api/v1/metrics?deployment_id=${deploymentId}&days=${days}`).then((r) => r.json()),
      fetch(`/api/v1/traces?deployment_id=${deploymentId}&page=${page}`).then((r) => r.json()),
    ]).then(([metricsData, tracesData]) => {
      setDaily((metricsData as { daily?: DailyMetric[] }).daily ?? []);
      setTraces((tracesData as { traces?: TraceRow[] }).traces ?? []);
      setTotal((tracesData as { total?: number }).total ?? 0);
      setLoading(false);
    }).catch(/* istanbul ignore next */ () => {
      setLoading(false);
    });
  }, [deploymentId, days, page]);

  // Derived summary metrics
  const totalCost = daily.reduce((s, d) => s + (d.total_cost_usd ?? 0), 0);
  const totalCalls = daily.reduce((s, d) => s + (d.call_count ?? 0), 0);
  const p95 = daily.length ? Math.max(...daily.map((d) => d.p95_latency_ms ?? 0)) : 0;
  const judgedDays = daily.filter((d) => d.avg_judge_score != null);
  const avgJudge =
    judgedDays.length > 0
      ? judgedDays.reduce((s, d) => s + (d.avg_judge_score ?? 0), 0) / judgedDays.length
      : null;

  return (
    <div className="mt-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-white">[6] OBSERVE</h3>
        <select
          value={days}
          onChange={(e) => { setDays(Number(e.target.value)); setPage(1); }}
          className="bg-gray-800 border border-gray-700 text-gray-300 text-xs rounded px-2 py-1"
        >
          <option value={7}>최근 7일</option>
          <option value={30}>최근 30일</option>
        </select>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-4 gap-3 mb-4">
        <MetricCard label="총 비용" value={`$${totalCost.toFixed(4)}`} color="green" />
        <MetricCard label="P95 지연" value={`${p95.toLocaleString()}ms`} color="indigo" />
        <MetricCard label="호출 수" value={totalCalls.toLocaleString()} color="yellow" />
        <MetricCard
          label="평균 Judge"
          value={avgJudge != null ? avgJudge.toFixed(2) : "—"}
          color="red"
        />
      </div>

      {/* Daily Bar Chart */}
      {daily.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 mb-4">
          <p className="text-xs text-gray-500 mb-2">일별 비용 (USD)</p>
          <ResponsiveContainer width="100%" height={80}>
            <BarChart data={daily} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis
                dataKey="date"
                tick={{ fill: "#6b7280", fontSize: 10 }}
                tickFormatter={(v: string) => v.slice(5)}
              />
              <YAxis tick={{ fill: "#6b7280", fontSize: 10 }} />
              <Tooltip
                contentStyle={{ background: "#111827", border: "1px solid #374151", fontSize: 12 }}
                formatter={(value: number, name: string) => [
                  name === "total_cost_usd" ? `$${Number(value).toFixed(4)}` : value,
                  name === "total_cost_usd" ? "비용" : "호출",
                ]}
              />
              <Bar dataKey="total_cost_usd" fill="#4ade80" radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Trace Table */}
      <div className="border border-gray-800 rounded-lg overflow-hidden">
        <div className="grid grid-cols-6 gap-2 bg-gray-900 px-3 py-2 text-xs text-gray-500 border-b border-gray-800">
          <span className="col-span-2">Trace ID</span>
          <span>Variant</span>
          <span>지연</span>
          <span>비용</span>
          <span>Judge / 피드백</span>
        </div>
        {loading ? (
          <div className="px-3 py-4 text-center text-xs text-gray-500">{t("trace", "loading")}</div>
        ) : traces.length === 0 ? (
          <div className="px-3 py-4 text-center text-xs text-gray-500">
            아직 trace가 없습니다. ArcanaInsight에서 client.record()를 호출하면 여기 표시됩니다.
          </div>
        ) : (
          traces.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setSelectedTraceId(t.id)}
              className="grid grid-cols-6 gap-2 px-3 py-2 text-xs text-gray-300 border-b border-gray-900 cursor-pointer hover:bg-gray-800 transition-colors w-full text-left"
            >
              <span className="col-span-2 font-mono text-blue-400 truncate">{t.id}</span>
              <span className={t.variant === "baseline" ? "text-gray-400" : "text-green-400"}>
                {t.variant}
              </span>
              <span>{t.latency_ms?.toLocaleString()}ms</span>
              <span>${Number(t.cost_usd).toFixed(4)}</span>
              <span>
                {t.judge_score != null ? (
                  <span className={t.judge_score >= 0.7 ? "text-green-400" : "text-yellow-400"}>
                    {t.judge_score.toFixed(2)}
                  </span>
                ) : (
                  <span className="text-gray-500 italic">채점 중...</span>
                )}{" "}
                {t.user_feedback === 1 ? "👍" : t.user_feedback === -1 ? "👎" : ""}
              </span>
            </button>
          ))
        )}
      </div>

      {/* Pagination */}
      {total > 20 && (
        <div className="flex justify-between items-center mt-3 text-xs text-gray-500">
          <span>총 {total.toLocaleString()}개</span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-2 py-1 bg-gray-800 rounded disabled:opacity-40"
            >
              이전
            </button>
            <span className="px-2 py-1">{page}</span>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={page * 20 >= total}
              className="px-2 py-1 bg-gray-800 rounded disabled:opacity-40"
            >
              다음
            </button>
          </div>
        </div>
      )}

      {/* Span Waterfall Slide-over */}
      {selectedTraceId && (
        <SpanWaterfall
          traceId={selectedTraceId}
          onClose={() => setSelectedTraceId(null)}
        />
      )}
    </div>
  );
}

function MetricCard({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color: "green" | "indigo" | "yellow" | "red";
}) {
  const colors = {
    green: "border-green-800 text-green-400",
    indigo: "border-indigo-800 text-indigo-400",
    yellow: "border-yellow-800 text-yellow-400",
    red: "border-red-800 text-red-400",
  };
  return (
    <div className={`bg-gray-950 border rounded-lg p-3 ${colors[color]}`}>
      <div className="text-lg font-bold">{value}</div>
      <div className="text-xs text-gray-500 mt-1">{label}</div>
    </div>
  );
}
