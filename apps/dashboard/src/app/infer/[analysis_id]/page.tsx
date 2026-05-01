import { notFound, redirect } from "next/navigation";
import { auth } from "@/auth";
import { getInference, getHarvestSources, type HarvestSource } from "@/lib/db/queries";

export default async function InferPage({
  params,
  searchParams,
}: {
  params: Promise<{ analysis_id: string }>;
  searchParams: Promise<{ inference_id?: string }>;
}) {
  const session = await auth();
  if (!session?.user) redirect("/login");

  const userId = String((session.user as Record<string, unknown>).id ?? "");
  if (!userId) redirect("/login");

  const { analysis_id } = await params;
  const { inference_id } = await searchParams;

  if (!inference_id) notFound();

  const data = await getInference(userId, inference_id);
  if (!data) notFound();

  const sources = data.status === "done" ? await getHarvestSources(inference_id) : [];

  return (
    <main className="max-w-[720px] mx-auto mt-10 font-mono px-4">
      <a href={`/analyses/${analysis_id}`} style={{ fontSize: 12, color: "#666" }}>← Back to analysis</a>
      <h1 style={{ fontSize: 22, margin: "16px 0 4px" }}>INFER — Service Domain</h1>

      {(data.status === "pending" || data.status === "running") && (
        <div>
          <p style={{ color: "#888" }}>Inference in progress…</p>
          <p><a href={`/infer/${analysis_id}?inference_id=${inference_id}`}>Refresh</a></p>
        </div>
      )}

      {data.status === "error" && (
        <p style={{ color: "red" }}>Error: {data.error}</p>
      )}

      {data.status === "done" && (
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

          <h2 style={{ fontSize: 16, marginBottom: 8 }}>Knowledge Sources ({sources.length})</h2>
          <p style={{ fontSize: 12, color: "#888", marginBottom: 16 }}>
            These sources were identified and are being crawled automatically.
          </p>

          {sources.map((src) => (
            <SourceCard key={src.id} source={src} />
          ))}

          <div style={{ marginTop: 24 }}>
            <a
              href={`/harvest/${inference_id}`}
              style={{ display: "inline-block", padding: "10px 20px", background: "#d97706", color: "white", textDecoration: "none", fontWeight: "bold", fontSize: 14 }}
            >
              View HARVEST progress →
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

function SourceCard({ source }: { source: HarvestSource }) {
  const statusColor =
    source.status === "approved" ? "#22c55e" :
    source.status === "rejected" ? "#ef4444" : "#888";

  const statusLabel =
    source.status === "approved" ? "crawling" :
    source.status === "rejected" ? "skipped" : "pending";

  return (
    <div style={{ border: "1px solid #ddd", padding: "12px 16px", marginBottom: 8 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: "bold", marginBottom: 4, fontSize: 14 }}>{source.title ?? source.url}</div>
          <div style={{ fontSize: 12, color: "#666", marginBottom: 4 }}>{source.url}</div>
          {source.description && <div style={{ fontSize: 12, color: "#888" }}>{source.description}</div>}
        </div>
        <span style={{ fontSize: 12, color: statusColor, fontWeight: "bold", marginLeft: 16 }}>{statusLabel}</span>
      </div>
    </div>
  );
}
