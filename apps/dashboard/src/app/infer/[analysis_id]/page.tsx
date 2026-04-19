import { notFound } from "next/navigation";
import { apiFetch, ApiError } from "@/lib/api";

interface Source {
  source_id: string;
  url: string;
  title: string | null;
  description: string | null;
  status: string;
}

interface InferData {
  status: string;
  inference_id?: string;
  analysis_id?: string;
  domain?: string;
  tone?: string;
  language?: string;
  user_type?: string;
  confidence?: number;
  summary?: string;
  suggested_sources?: Source[];
  error?: string;
}

async function startInfer(analysisId: string): Promise<InferData> {
  try {
    return await apiFetch<InferData>(`/v1/infer/${analysisId}`, {
      method: "POST",
    });
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) notFound();
    throw err;
  }
}

async function getInfer(inferenceId: string): Promise<InferData> {
  try {
    return await apiFetch<InferData>(`/v1/infer/${inferenceId}`);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) notFound();
    throw err;
  }
}

async function approveSource(sourceId: string): Promise<void> {
  await apiFetch(`/v1/sources/${sourceId}/approve`, { method: "POST" });
}

async function rejectSource(sourceId: string): Promise<void> {
  await apiFetch(`/v1/sources/${sourceId}/reject`, { method: "POST" });
}

export default async function InferPage({
  params,
  searchParams,
}: {
  params: Promise<{ analysis_id: string }>;
  searchParams: Promise<{ inference_id?: string }>;
}) {
  const { analysis_id } = await params;
  const { inference_id } = await searchParams;

  let data: InferData;

  if (inference_id) {
    data = await getInfer(inference_id);
  } else {
    const started = await startInfer(analysis_id);
    data = started;
  }

  return (
    <main style={{ maxWidth: 720, margin: "40px auto", fontFamily: "monospace", padding: "0 16px" }}>
      <a href={`/analyses/${analysis_id}`} style={{ fontSize: 12, color: "#666" }}>← Back to analysis</a>
      <h1 style={{ fontSize: 22, margin: "16px 0 4px" }}>INFER — Service Domain</h1>

      {(data.status === "pending" || data.status === "running") && (
        <div>
          <p style={{ color: "#888" }}>Inference in progress (inference_id: {data.inference_id})…</p>
          <p>
            <a href={`/infer/${analysis_id}?inference_id=${data.inference_id}`}>Refresh</a>
          </p>
        </div>
      )}

      {data.status === "error" && (
        <p style={{ color: "red" }}>Error: {data.error}</p>
      )}

      {data.status === "done" && data.inference_id && (
        <div>
          <table style={{ borderCollapse: "collapse", marginBottom: 24, fontSize: 14 }}>
            <tbody>
              <InfoRow label="Domain" value={data.domain ?? "—"} />
              <InfoRow label="Tone" value={data.tone ?? "—"} />
              <InfoRow label="Language" value={data.language ?? "—"} />
              <InfoRow label="User type" value={data.user_type ?? "—"} />
              <InfoRow label="Confidence" value={`${((data.confidence ?? 0) * 100).toFixed(0)}%`} />
            </tbody>
          </table>

          {data.summary && (
            <p style={{ marginBottom: 24, color: "#444", lineHeight: 1.5 }}>{data.summary}</p>
          )}

          <h2 style={{ fontSize: 16, marginBottom: 12 }}>
            Suggested Sources ({data.suggested_sources?.length ?? 0})
          </h2>
          <p style={{ fontSize: 12, color: "#888", marginBottom: 16 }}>
            Approve sources you want Verum to crawl for knowledge.
          </p>

          {(data.suggested_sources ?? []).map((src) => (
            <SourceCard
              key={src.source_id}
              source={src}
            />
          ))}

          <div style={{ marginTop: 24 }}>
            <a
              href={`/harvest/${data.inference_id}`}
              style={{
                display: "inline-block",
                padding: "10px 20px",
                background: "#0066cc",
                color: "white",
                textDecoration: "none",
                fontWeight: "bold",
                fontSize: 14,
              }}
            >
              Start HARVEST →
            </a>
          </div>
        </div>
      )}
    </main>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <tr>
      <td style={{ padding: "4px 16px 4px 0", fontWeight: "bold", color: "#555" }}>{label}</td>
      <td style={{ padding: "4px 0" }}>{value}</td>
    </tr>
  );
}

function SourceCard({
  source,
}: {
  source: Source;
}) {
  const statusColor =
    source.status === "approved" ? "#22c55e" :
    source.status === "rejected" ? "#ef4444" : "#888";

  const sourceId = source.source_id;

  return (
    <div style={{ border: "1px solid #ddd", padding: "12px 16px", marginBottom: 8 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: "bold", marginBottom: 4, fontSize: 14 }}>
            {source.title ?? source.url}
          </div>
          <div style={{ fontSize: 12, color: "#666", marginBottom: 4 }}>{source.url}</div>
          {source.description && (
            <div style={{ fontSize: 12, color: "#888" }}>{source.description}</div>
          )}
        </div>
        <span style={{ fontSize: 12, color: statusColor, fontWeight: "bold", marginLeft: 16 }}>
          {source.status}
        </span>
      </div>
      {source.status === "proposed" && (
        <div style={{ marginTop: 8, display: "flex", gap: 8 }}>
          <form action={async () => { "use server"; await approveSource(sourceId); }}>
            <button type="submit" style={{ padding: "4px 12px", fontSize: 12, fontWeight: "bold", border: "1px solid #22c55e", color: "#22c55e", background: "white", cursor: "pointer" }}>
              Approve
            </button>
          </form>
          <form action={async () => { "use server"; await rejectSource(sourceId); }}>
            <button type="submit" style={{ padding: "4px 12px", fontSize: 12, fontWeight: "bold", border: "1px solid #ef4444", color: "#ef4444", background: "white", cursor: "pointer" }}>
              Reject
            </button>
          </form>
        </div>
      )}
    </div>
  );
}
