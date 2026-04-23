import { notFound, redirect } from "next/navigation";
import { auth } from "@/auth";
import { enqueueGenerate, approveGeneration } from "@/lib/db/jobs";
import { getInference, getLatestGeneration, getGenerationFull } from "@/lib/db/queries";
import { t } from "@/lib/i18n";

function isMetricProfile(
  v: unknown,
): v is { primary_metrics: string[]; secondary_metrics: string[]; profile_name: string } {
  return (
    v !== null &&
    typeof v === "object" &&
    "primary_metrics" in v &&
    "secondary_metrics" in v &&
    "profile_name" in v &&
    Array.isArray((v as Record<string, unknown>).primary_metrics) &&
    Array.isArray((v as Record<string, unknown>).secondary_metrics)
  );
}

export default async function GeneratePage({
  params,
}: {
  params: Promise<{ inference_id: string }>;
}) {
  const session = await auth();
  if (!session?.user) redirect("/login");
  const uid = String((session.user as Record<string, unknown>).id ?? "");
  if (!uid) redirect("/login");

  const { inference_id } = await params;

  const inference = await getInference(uid, inference_id);
  if (!inference) notFound();

  const latestGen = await getLatestGeneration(inference_id);
  const full = latestGen ? await getGenerationFull(uid, latestGen.id) : null;
  const rawProfile = full?.gen?.metric_profile;
  const metricProfile = isMetricProfile(rawProfile) ? rawProfile : null;

  async function triggerGenerate() {
    "use server";
    const session = await auth();
    if (!session?.user) return;
    const uid = String((session.user as Record<string, unknown>).id ?? "");
    if (!uid) return;
    await enqueueGenerate({ userId: uid, inferenceId: inference_id });
    redirect(`/generate/${inference_id}`);
  }

  async function triggerApprove(formData: FormData) {
    "use server";
    const genId = formData.get("generation_id") as string;
    if (!genId) return;
    const session = await auth();
    if (!session?.user) return;
    const uid = String((session.user as Record<string, unknown>).id ?? "");
    if (!uid) return;
    await approveGeneration(uid, genId);
    redirect(`/deploy/${genId}`);
  }

  return (
    <main style={{ maxWidth: 800, margin: "40px auto", fontFamily: "monospace", padding: "0 16px" }}>
      <h1 style={{ fontSize: 22, margin: "16px 0 4px" }}>GENERATE — Asset Generation</h1>
      <p style={{ color: "#666", fontSize: 13, marginBottom: 24 }}>
        Domain: <strong>{inference.domain ?? "—"}</strong> · Tone: {inference.tone ?? "—"} · Language: {inference.language ?? "—"}
      </p>

      {(!latestGen || latestGen.status === "error") && (
        <form action={triggerGenerate}>
          <button
            type="submit"
            style={{ background: "#000", color: "#fff", border: "none", padding: "10px 20px", cursor: "pointer", fontSize: 14 }}
          >
            {t("generate", "startButton")}
          </button>
        </form>
      )}

      {latestGen && (
        <>
          <div style={{ marginBottom: 16, padding: "8px 12px", background: "#f9f9f9", border: "1px solid #ddd", fontSize: 13 }}>
            Status: <strong>{latestGen.status}</strong>
            {latestGen.status === "pending" && (
              <span style={{ marginLeft: 12, color: "#888" }}>
                {t("generate", "generating")} <a href={`/generate/${inference_id}`}>{t("generate", "refresh")}</a>
              </span>
            )}
          </div>

          {metricProfile && (
            <div style={{ marginBottom: 20 }}>
              <h2 style={{ fontSize: 14, marginBottom: 6 }}>{t("generate", "metricProfileHeading")} — {metricProfile.profile_name}</h2>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                {metricProfile.primary_metrics.map((m) => (
                  <span key={m} style={{ background: "#e0f2fe", padding: "2px 8px", fontSize: 12, borderRadius: 4 }}>{m}</span>
                ))}
                {metricProfile.secondary_metrics.map((m) => (
                  <span key={m} style={{ background: "#f3f4f6", padding: "2px 8px", fontSize: 12, borderRadius: 4, color: "#666" }}>{m}</span>
                ))}
              </div>
            </div>
          )}

          {full && full.variants.length > 0 && (
            <div style={{ marginBottom: 24 }}>
              <h2 style={{ fontSize: 15, marginBottom: 8 }}>{t("generate", "promptVariantsHeading")} ({full.variants.length})</h2>
              {full.variants.map((v) => (
                <details key={v.id} style={{ marginBottom: 8, border: "1px solid #ddd", padding: "8px 12px" }}>
                  <summary style={{ cursor: "pointer", fontSize: 13, fontWeight: "bold" }}>{v.variant_type}</summary>
                  <pre style={{ whiteSpace: "pre-wrap", fontSize: 12, marginTop: 8, color: "#333" }}>{v.content}</pre>
                </details>
              ))}
            </div>
          )}

          {full?.rag && (
            <div style={{ marginBottom: 24 }}>
              <h2 style={{ fontSize: 15, marginBottom: 8 }}>RAG Config</h2>
              <table style={{ fontSize: 13, borderCollapse: "collapse" }}>
                {Object.entries(full.rag)
                  .filter(([k]) => k !== "id" && k !== "generation_id" && k !== "created_at")
                  .map(([k, v]) => (
                    <tr key={k}>
                      <td style={{ padding: "2px 12px 2px 0", color: "#666" }}>{k}</td>
                      <td style={{ padding: "2px 0" }}>{String(v)}</td>
                    </tr>
                  ))}
              </table>
            </div>
          )}

          {full && full.pairs.length > 0 && (
            <div style={{ marginBottom: 24 }}>
              <h2 style={{ fontSize: 15, marginBottom: 8 }}>{t("generate", "evalPairsHeading")}</h2>
              {full.pairs.map((p, i) => (
                <div key={p.id} style={{ marginBottom: 8, padding: "8px 12px", background: "#f9f9f9", border: "1px solid #ddd", fontSize: 12 }}>
                  <strong>Q{i + 1}:</strong> {p.query}<br />
                  <span style={{ color: "#555" }}>A: {p.expected_answer}</span>
                </div>
              ))}
            </div>
          )}

          {latestGen.status === "done" && (
            <form action={triggerApprove}>
              <input type="hidden" name="generation_id" value={latestGen.id} />
              <button
                type="submit"
                style={{ background: "#16a34a", color: "#fff", border: "none", padding: "10px 24px", cursor: "pointer", fontSize: 14 }}
              >
                {t("generate", "approveButton")}
              </button>
            </form>
          )}
        </>
      )}
    </main>
  );
}
