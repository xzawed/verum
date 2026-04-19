import { notFound, redirect } from "next/navigation";
import { auth } from "@/auth";
import { getAnalysis } from "@/lib/db/queries";

interface CallSite {
  file_path: string;
  line: number;
  sdk: string;
  function: string;
  prompt_ref: string | null;
}

interface PromptTemplate {
  id: string;
  file_path: string;
  line: number;
  content: string;
  language: string;
  variables: string[];
}

interface ModelConfig {
  file_path: string;
  line: number;
  model: string | null;
  temperature: number | null;
  max_tokens: number | null;
}

export default async function AnalysisPage({ params }: { params: Promise<{ id: string }> }) {
  const session = await auth();
  if (!session?.user) redirect("/login");

  const userId = String((session.user as Record<string, unknown>).id ?? "");
  if (!userId) redirect("/login");

  const { id } = await params;
  const data = await getAnalysis(userId, id);
  if (!data) notFound();

  if (data.status === "pending" || data.status === "running") {
    return (
      <main style={{ maxWidth: 700, margin: "80px auto", fontFamily: "monospace", padding: "0 16px" }}>
        <h1 style={{ fontSize: 24, marginBottom: 8 }}>Analysis in progress</h1>
        <p style={{ color: "#666" }}>Status: {data.status}</p>
        {data.started_at && <p style={{ color: "#666" }}>Started: {new Date(data.started_at).toLocaleString()}</p>}
        <p style={{ marginTop: 24 }}>
          <a href={`/analyses/${data.id}`}>Refresh</a>
        </p>
      </main>
    );
  }

  if (data.status === "error") {
    return (
      <main style={{ maxWidth: 700, margin: "80px auto", fontFamily: "monospace", padding: "0 16px" }}>
        <h1 style={{ fontSize: 24, marginBottom: 8, color: "red" }}>Analysis failed</h1>
        <pre style={{ background: "#fee", padding: 12, overflowX: "auto" }}>{data.error}</pre>
        <p><a href="/repos">Back to repos</a></p>
      </main>
    );
  }

  const callSites = (data.call_sites as CallSite[]) ?? [];
  const promptTemplates = (data.prompt_templates as PromptTemplate[]) ?? [];
  const modelConfigs = (data.model_configs as ModelConfig[]) ?? [];
  const languageBreakdown = (data.language_breakdown as Record<string, number>) ?? {};

  const byFile = callSites.reduce<Record<string, CallSite[]>>((acc, cs) => {
    (acc[cs.file_path] ??= []).push(cs);
    return acc;
  }, {});

  return (
    <main style={{ maxWidth: 800, margin: "40px auto", fontFamily: "monospace", padding: "0 16px" }}>
      <a href="/repos" style={{ fontSize: 12, color: "#666" }}>← My Repos</a>
      <h1 style={{ fontSize: 24, margin: "16px 0 4px" }}>Analysis complete</h1>
      <p style={{ color: "#666", marginBottom: 24 }}>
        {callSites.length} call site{callSites.length !== 1 ? "s" : ""} detected
        {data.analyzed_at ? ` · ${new Date(data.analyzed_at).toLocaleString()}` : ""}
      </p>

      {Object.keys(languageBreakdown).length > 0 && (
        <section style={{ marginBottom: 32 }}>
          <h2 style={{ fontSize: 16, marginBottom: 8 }}>Language breakdown</h2>
          <table style={{ borderCollapse: "collapse", fontSize: 13 }}>
            <tbody>
              {Object.entries(languageBreakdown)
                .sort(([, a], [, b]) => b - a)
                .map(([lang, count]) => (
                  <tr key={lang}>
                    <td style={{ padding: "2px 16px 2px 0", fontWeight: "bold" }}>{lang}</td>
                    <td style={{ padding: "2px 0", color: "#444" }}>{count} files</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </section>
      )}

      <section style={{ marginBottom: 32 }}>
        <h2 style={{ fontSize: 16, marginBottom: 8 }}>LLM Call Sites ({callSites.length})</h2>
        {Object.entries(byFile).map(([filePath, sites]) => (
          <div key={filePath} style={{ marginBottom: 16 }}>
            <div style={{ color: "#555", fontSize: 12, marginBottom: 4 }}>{filePath}</div>
            {sites.map((cs, i) => (
              <div key={i} style={{ padding: "6px 12px", background: "#f5f5f5", marginBottom: 4, fontSize: 13 }}>
                <span style={{ fontWeight: "bold", color: "#0066cc" }}>[{cs.sdk}]</span>{" "}
                line {cs.line} — {cs.function}
                {cs.prompt_ref && <span style={{ color: "#888", marginLeft: 8 }}>prompt: {cs.prompt_ref.slice(0, 8)}…</span>}
              </div>
            ))}
          </div>
        ))}
        {callSites.length === 0 && <p style={{ color: "#888" }}>No LLM call sites detected.</p>}
      </section>

      {promptTemplates.length > 0 && (
        <section style={{ marginBottom: 32 }}>
          <h2 style={{ fontSize: 16, marginBottom: 8 }}>Prompt Templates ({promptTemplates.length})</h2>
          {promptTemplates.map((pt) => (
            <div key={pt.id} style={{ marginBottom: 16, padding: "10px 12px", background: "#f9f9f9", border: "1px solid #ddd" }}>
              <div style={{ fontSize: 12, color: "#555", marginBottom: 6 }}>
                {pt.file_path}:{pt.line} · {pt.language}
                {pt.variables.length > 0 && ` · vars: ${pt.variables.join(", ")}`}
              </div>
              <pre style={{ fontSize: 12, whiteSpace: "pre-wrap", wordBreak: "break-word", margin: 0, maxHeight: 120, overflow: "hidden" }}>
                {pt.content.slice(0, 400)}{pt.content.length > 400 ? "…" : ""}
              </pre>
            </div>
          ))}
        </section>
      )}

      {modelConfigs.length > 0 && (
        <section style={{ marginBottom: 32 }}>
          <h2 style={{ fontSize: 16, marginBottom: 8 }}>Model Configs ({modelConfigs.length})</h2>
          {modelConfigs.map((mc, i) => (
            <div key={i} style={{ fontSize: 13, padding: "6px 12px", background: "#f5f5f5", marginBottom: 4 }}>
              {mc.file_path}:{mc.line}
              {mc.model && <span style={{ marginLeft: 8, fontWeight: "bold" }}>{mc.model}</span>}
              {mc.temperature != null && <span style={{ marginLeft: 8, color: "#555" }}>temp={mc.temperature}</span>}
              {mc.max_tokens != null && <span style={{ marginLeft: 8, color: "#555" }}>max_tokens={mc.max_tokens}</span>}
            </div>
          ))}
        </section>
      )}
    </main>
  );
}
