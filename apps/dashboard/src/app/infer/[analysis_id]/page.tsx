import { notFound } from "next/navigation";

const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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
  const res = await fetch(`${apiBase}/v1/infer/${analysisId}`, {
    method: "POST",
    cache: "no-store",
  });
  if (res.status === 404) notFound();
  return res.json();
}

async function getInfer(inferenceId: string): Promise<InferData> {
  const res = await fetch(`${apiBase}/v1/infer/${inferenceId}`, {
    cache: "no-store",
  });
  if (res.status === 404) notFound();
  return res.json();
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
    // Trigger a new inference
    const started = await startInfer(analysis_id);
    if (started.inference_id) {
      // Wait briefly then fetch result (server-side polling not ideal — redirect to status page)
      data = started;
    } else {
      data = started;
    }
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
            Approve sources you want Verum to crawl for knowledge. Rejected sources will not be crawled.
          </p>

          {(data.suggested_sources ?? []).map((src) => (
            <SourceCard
              key={src.source_id}
              source={src}
              inferenceId={data.inference_id!}
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

function SourceCard({ source, inferenceId }: { source: Source; inferenceId: string }) {
  const statusColor =
    source.status === "approved" ? "#22c55e" :
    source.status === "rejected" ? "#ef4444" : "#888";

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
        <div style={{ marginLeft: 16, display: "flex", gap: 8, flexShrink: 0 }}>
          <span style={{ fontSize: 12, color: statusColor, fontWeight: "bold" }}>
            {source.status}
          </span>
        </div>
      </div>
      {source.status === "proposed" && (
        <div style={{ marginTop: 8, display: "flex", gap: 8 }}>
          <ApproveButton sourceId={source.source_id} action="approve" />
          <ApproveButton sourceId={source.source_id} action="reject" />
        </div>
      )}
    </div>
  );
}

function ApproveButton({ sourceId, action }: { sourceId: string; action: "approve" | "reject" }) {
  const label = action === "approve" ? "Approve" : "Reject";
  const color = action === "approve" ? "#22c55e" : "#ef4444";
  return (
    <form action={`/api/sources/${sourceId}/${action}`} method="POST">
      <button
        type="submit"
        style={{
          padding: "4px 12px",
          fontSize: 12,
          fontWeight: "bold",
          border: `1px solid ${color}`,
          color,
          background: "white",
          cursor: "pointer",
        }}
      >
        {label}
      </button>
    </form>
  );
}
