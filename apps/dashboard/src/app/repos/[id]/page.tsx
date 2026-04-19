import { redirect } from "next/navigation";
import { auth } from "@/auth";
import { enqueueAnalyze, enqueueInfer, enqueueHarvest } from "@/lib/db/jobs";
import { getRepoStatus, getHarvestSources } from "@/lib/db/queries";

export default async function RepoDashboardPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const session = await auth();
  if (!session?.user) redirect("/login");

  const u = session.user as Record<string, unknown>;
  const userId = String(u.id ?? "");
  if (!userId) redirect("/login");

  const { id } = await params;
  const status = await getRepoStatus(userId, id);
  if (!status) redirect("/repos");

  const { repo, latestAnalysis, latestInference, harvestChunks, harvestSourcesDone, harvestSourcesTotal } = status;
  const repoName = repo.github_url.replace("https://github.com/", "");

  return (
    <main style={{ maxWidth: 840, margin: "40px auto", fontFamily: "monospace", padding: "0 16px" }}>
      <a href="/repos" style={{ fontSize: 12, color: "#666" }}>← My Repos</a>
      <h1 style={{ fontSize: 22, margin: "12px 0 4px" }}>{repoName}</h1>
      <p style={{ fontSize: 12, color: "#888", marginBottom: 32 }}>
        {repo.github_url} · branch: {repo.default_branch}
      </p>

      {/* ── ANALYZE ── */}
      <Section title="[1] ANALYZE" color="#0066cc">
        {latestAnalysis ? (
          <div>
            <StatusRow label="Status" value={latestAnalysis.status} />
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
        <form
          action={async () => {
            "use server";
            const s = await auth();
            if (!s?.user) redirect("/login");
            const uid = String((s.user as Record<string, unknown>).id ?? "");
            const analysis = await enqueueAnalyze({
              userId: uid,
              repoId: id,
              repoUrl: repo.github_url,
              branch: repo.default_branch,
            });
            redirect(`/analyses/${analysis.id}`);
          }}
          style={{ marginTop: 12 }}
        >
          <button type="submit" style={btnStyle}>
            {latestAnalysis ? "Re-run ANALYZE" : "Run ANALYZE"}
          </button>
        </form>
      </Section>

      {/* ── INFER ── */}
      <Section title="[2] INFER" color="#7c3aed">
        {latestInference ? (
          <div>
            <StatusRow label="Status" value={latestInference.status} />
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
          <form
            action={async () => {
              "use server";
              const s = await auth();
              if (!s?.user) redirect("/login");
              const uid = String((s.user as Record<string, unknown>).id ?? "");
              const inference = await enqueueInfer({
                userId: uid,
                repoId: repo.id,
                analysisId: latestAnalysis.id,
              });
              redirect(`/infer/${latestAnalysis.id}?inference_id=${inference.id}`);
            }}
            style={{ marginTop: 12 }}
          >
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
            {latestInference?.status === "done" ? "Approve sources in INFER first." : "Run INFER first."}
          </p>
        )}
        {latestInference?.status === "done" && (
          <form
            action={async () => {
              "use server";
              const s = await auth();
              if (!s?.user) redirect("/login");
              const uid = String((s.user as Record<string, unknown>).id ?? "");
              const sources = await getHarvestSources(latestInference.id);
              const approved = sources.filter((src) => src.status === "approved");
              if (approved.length === 0) redirect(`/infer/${latestAnalysis?.id}?inference_id=${latestInference.id}`);
              await enqueueHarvest({
                userId: uid,
                inferenceId: latestInference.id,
                sourcePairs: approved.map((src) => ({ sourceId: src.id, url: src.url })),
              });
              redirect(`/harvest/${latestInference.id}`);
            }}
            style={{ marginTop: 12 }}
          >
            <button type="submit" style={{ ...btnStyle, background: "#059669" }}>
              {harvestChunks > 0 ? "Re-trigger HARVEST" : "Run HARVEST"}
            </button>
          </form>
        )}
      </Section>
    </main>
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
