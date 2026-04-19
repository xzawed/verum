import { notFound, redirect } from "next/navigation";
import { auth } from "@/auth";
import { enqueueHarvest } from "@/lib/db/jobs";
import { getHarvestSources, countChunks, getInference } from "@/lib/db/queries";

export default async function HarvestPage({
  params,
  searchParams,
}: {
  params: Promise<{ inference_id: string }>;
  searchParams: Promise<{ trigger?: string }>;
}) {
  const session = await auth();
  if (!session?.user) redirect("/login");

  const userId = String((session.user as Record<string, unknown>).id ?? "");
  if (!userId) redirect("/login");

  const { inference_id } = await params;
  const { trigger } = await searchParams;

  const inference = await getInference(userId, inference_id);
  if (!inference) notFound();

  if (trigger === "1") {
    const sources = await getHarvestSources(inference_id);
    const approved = sources.filter((s) => s.status === "approved");
    if (approved.length > 0) {
      await enqueueHarvest({
        userId,
        inferenceId: inference_id,
        sourcePairs: approved.map((s) => ({ sourceId: s.id, url: s.url })),
      });
    }
    redirect(`/harvest/${inference_id}`);
  }

  const sources = await getHarvestSources(inference_id);
  const totalChunks = await countChunks(inference_id);
  const doneSources = sources.filter((s) => s.status === "done");
  const errorSources = sources.filter((s) => s.status === "error");
  const runningSources = sources.filter((s) => s.status === "crawling");

  return (
    <main style={{ maxWidth: 720, margin: "40px auto", fontFamily: "monospace", padding: "0 16px" }}>
      <h1 style={{ fontSize: 22, margin: "16px 0 4px" }}>HARVEST — Knowledge Collection</h1>

      <div style={{ display: "flex", gap: 32, marginBottom: 24, marginTop: 16 }}>
        <Stat label="Total chunks" value={totalChunks} />
        <Stat label="Done" value={doneSources.length} />
        <Stat label="Running" value={runningSources.length} />
        <Stat label="Errors" value={errorSources.length} />
      </div>

      {totalChunks >= 1000 && (
        <div style={{ background: "#f0fdf4", border: "1px solid #22c55e", padding: "12px 16px", marginBottom: 24 }}>
          <strong style={{ color: "#22c55e" }}>✓ Completion gate reached</strong>
          <span style={{ color: "#444", marginLeft: 8 }}>
            {totalChunks.toLocaleString()} chunks indexed — ready for GENERATE
          </span>
        </div>
      )}

      {runningSources.length > 0 && (
        <p style={{ color: "#888", marginBottom: 16, fontSize: 13 }}>
          Crawling in progress… <a href={`/harvest/${inference_id}`}>Refresh</a>
        </p>
      )}

      <h2 style={{ fontSize: 15, marginBottom: 8 }}>Sources</h2>
      {sources.map((src) => (
        <div
          key={src.id}
          style={{
            padding: "8px 12px",
            marginBottom: 6,
            background: src.status === "done" ? "#f0fdf4" : src.status === "error" ? "#fef2f2" : "#f9f9f9",
            border: "1px solid #ddd",
            fontSize: 13,
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span style={{ wordBreak: "break-all", flex: 1 }}>{src.url}</span>
            <span style={{ marginLeft: 12, fontWeight: "bold", flexShrink: 0 }}>
              {src.status === "done" ? `${src.chunks_count} chunks` : src.status}
            </span>
          </div>
          {src.error && <div style={{ color: "#ef4444", fontSize: 12, marginTop: 4 }}>{src.error}</div>}
        </div>
      ))}

      <div style={{ marginTop: 24 }}>
        <a
          href={`/harvest/${inference_id}?trigger=1`}
          style={{ display: "inline-block", padding: "8px 16px", border: "1px solid #0066cc", color: "#0066cc", textDecoration: "none", fontSize: 13, marginRight: 12 }}
        >
          Re-trigger HARVEST
        </a>
        <a
          href={`/retrieve?inference_id=${inference_id}`}
          style={{ display: "inline-block", padding: "8px 16px", background: "#0066cc", color: "white", textDecoration: "none", fontSize: 13, fontWeight: "bold" }}
        >
          Search knowledge →
        </a>
      </div>
    </main>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div style={{ fontSize: 24, fontWeight: "bold" }}>{value.toLocaleString()}</div>
      <div style={{ fontSize: 12, color: "#666" }}>{label}</div>
    </div>
  );
}
