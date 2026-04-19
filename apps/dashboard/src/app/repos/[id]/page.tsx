import { redirect } from "next/navigation";
import { apiFetch, ApiError } from "@/lib/api";

interface RepoStatus {
  repo: {
    repo_id: string;
    github_url: string;
    default_branch: string;
    last_analyzed_at: string | null;
    created_at: string;
  };
  latest_analysis: {
    analysis_id: string;
    status: string;
    call_sites_count: number | null;
    analyzed_at: string | null;
  } | null;
  latest_inference: {
    inference_id: string;
    status: string;
    domain: string | null;
    confidence: number | null;
    approved_sources: number;
    total_sources: number;
  } | null;
  latest_harvest: {
    inference_id: string;
    sources_done: number;
    sources_total: number;
    total_chunks: number;
  } | null;
}

async function fetchStatus(repoId: string): Promise<RepoStatus> {
  try {
    return await apiFetch<RepoStatus>(`/v1/me/repos/${repoId}/status`);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) redirect("/repos");
    if (err instanceof ApiError && err.status === 401) redirect("/login");
    throw err;
  }
}

export default async function RepoDashboardPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const status = await fetchStatus(id);
  const { repo, latest_analysis, latest_inference, latest_harvest } = status;
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
        {latest_analysis ? (
          <div>
            <StatusRow label="Status" value={latest_analysis.status} />
            {latest_analysis.call_sites_count != null && (
              <StatusRow label="Call sites" value={String(latest_analysis.call_sites_count)} />
            )}
            {latest_analysis.analyzed_at && (
              <StatusRow
                label="Analyzed"
                value={new Date(latest_analysis.analyzed_at).toLocaleString()}
              />
            )}
            {latest_analysis.status === "done" && (
              <a
                href={`/analyses/${latest_analysis.analysis_id}`}
                style={{ display: "inline-block", marginTop: 8, fontSize: 12, color: "#0066cc" }}
              >
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
            const res = await apiFetch<{ analysis_id: string }>("/v1/analyze", {
              method: "POST",
              body: JSON.stringify({ repo_url: repo.github_url, branch: repo.default_branch }),
            });
            redirect(`/analyses/${res.analysis_id}`);
          }}
          style={{ marginTop: 12 }}
        >
          <button type="submit" style={btnStyle}>
            {latest_analysis ? "Re-run ANALYZE" : "Run ANALYZE"}
          </button>
        </form>
      </Section>

      {/* ── INFER ── */}
      <Section title="[2] INFER" color="#7c3aed">
        {latest_inference ? (
          <div>
            <StatusRow label="Status" value={latest_inference.status} />
            {latest_inference.domain && (
              <StatusRow label="Domain" value={latest_inference.domain} />
            )}
            {latest_inference.confidence != null && (
              <StatusRow
                label="Confidence"
                value={`${(latest_inference.confidence * 100).toFixed(0)}%`}
              />
            )}
            <StatusRow
              label="Sources"
              value={`${latest_inference.approved_sources} approved / ${latest_inference.total_sources} total`}
            />
            {latest_inference.status === "done" && (
              <a
                href={`/infer/${latest_analysis?.analysis_id}?inference_id=${latest_inference.inference_id}`}
                style={{ display: "inline-block", marginTop: 8, fontSize: 12, color: "#7c3aed" }}
              >
                View inference + approve sources →
              </a>
            )}
          </div>
        ) : (
          <p style={{ color: "#888", fontSize: 13 }}>
            {latest_analysis?.status === "done"
              ? "Analysis complete — ready to infer."
              : "Run ANALYZE first."}
          </p>
        )}
        {latest_analysis?.status === "done" && (
          <form
            action={async () => {
              "use server";
              const res = await apiFetch<{ inference_id: string }>(
                `/v1/infer/${latest_analysis.analysis_id}`,
                { method: "POST" }
              );
              redirect(`/infer/${latest_analysis.analysis_id}?inference_id=${res.inference_id}`);
            }}
            style={{ marginTop: 12 }}
          >
            <button type="submit" style={{ ...btnStyle, background: "#7c3aed" }}>
              {latest_inference ? "Re-run INFER" : "Run INFER"}
            </button>
          </form>
        )}
      </Section>

      {/* ── HARVEST ── */}
      <Section title="[3] HARVEST" color="#059669">
        {latest_harvest ? (
          <div>
            <StatusRow
              label="Sources"
              value={`${latest_harvest.sources_done} done / ${latest_harvest.sources_total} total`}
            />
            <StatusRow
              label="Chunks"
              value={latest_harvest.total_chunks.toLocaleString()}
            />
            {latest_inference?.inference_id && (
              <div style={{ marginTop: 8, display: "flex", gap: 12 }}>
                <a
                  href={`/harvest/${latest_inference.inference_id}`}
                  style={{ fontSize: 12, color: "#059669" }}
                >
                  View harvest status →
                </a>
                <a
                  href={`/retrieve?inference_id=${latest_inference.inference_id}`}
                  style={{ fontSize: 12, color: "#059669" }}
                >
                  Search knowledge →
                </a>
              </div>
            )}
          </div>
        ) : (
          <p style={{ color: "#888", fontSize: 13 }}>
            {latest_inference?.approved_sources
              ? "Sources approved — ready to harvest."
              : "Approve sources in INFER first."}
          </p>
        )}
        {latest_inference?.status === "done" && latest_inference.approved_sources > 0 && (
          <form
            action={async () => {
              "use server";
              await apiFetch(`/v1/harvest/${latest_inference.inference_id}`, { method: "POST" });
              redirect(`/harvest/${latest_inference.inference_id}`);
            }}
            style={{ marginTop: 12 }}
          >
            <button type="submit" style={{ ...btnStyle, background: "#059669" }}>
              {latest_harvest ? "Re-trigger HARVEST" : "Run HARVEST"}
            </button>
          </form>
        )}
      </Section>
    </main>
  );
}

function Section({
  title,
  color,
  children,
}: {
  title: string;
  color: string;
  children: React.ReactNode;
}) {
  return (
    <div
      style={{
        borderLeft: `3px solid ${color}`,
        paddingLeft: 16,
        marginBottom: 32,
      }}
    >
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
