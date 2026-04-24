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
    <main className="max-w-[800px] mx-auto mt-10 font-mono px-4">
      <h1 className="text-2xl mt-4 mb-1">GENERATE — Asset Generation</h1>
      <p className="text-gray-500 text-sm mb-6">
        Domain: <strong>{inference.domain ?? "—"}</strong> · Tone: {inference.tone ?? "—"} · Language: {inference.language ?? "—"}
      </p>

      {(!latestGen || latestGen.status === "error") && (
        <form action={triggerGenerate}>
          <button
            type="submit"
            className="bg-black text-white border-0 px-5 py-2.5 cursor-pointer text-sm"
          >
            {t("generate", "startButton")}
          </button>
        </form>
      )}

      {latestGen && (
        <>
          <div className="mb-4 px-3 py-2 bg-gray-50 border border-gray-200 text-sm">
            Status: <strong>{latestGen.status}</strong>
            {latestGen.status === "pending" && (
              <span className="ml-3 text-gray-400">
                {t("generate", "generating")} <a href={`/generate/${inference_id}`}>{t("generate", "refresh")}</a>
              </span>
            )}
          </div>

          {metricProfile && (
            <div className="mb-5">
              <h2 className="text-sm mb-1.5">{t("generate", "metricProfileHeading")} — {metricProfile.profile_name}</h2>
              <div className="flex gap-2 flex-wrap">
                {metricProfile.primary_metrics.map((m) => (
                  <span key={m} className="bg-sky-100 px-2 py-0.5 text-xs rounded">{m}</span>
                ))}
                {metricProfile.secondary_metrics.map((m) => (
                  <span key={m} className="bg-gray-100 px-2 py-0.5 text-xs rounded text-gray-500">{m}</span>
                ))}
              </div>
            </div>
          )}

          {full && full.variants.length > 0 && (
            <div className="mb-6">
              <h2 className="text-sm mb-2">{t("generate", "promptVariantsHeading")} ({full.variants.length})</h2>
              {full.variants.map((v) => (
                <details key={v.id} className="mb-2 border border-gray-200 px-3 py-2">
                  <summary className="cursor-pointer text-sm font-bold">{v.variant_type}</summary>
                  <pre className="whitespace-pre-wrap text-xs mt-2 text-gray-700">{v.content}</pre>
                </details>
              ))}
            </div>
          )}

          {full?.rag && (
            <div className="mb-6">
              <h2 className="text-sm mb-2">RAG Config</h2>
              <table className="text-sm border-collapse">
                {Object.entries(full.rag)
                  .filter(([k]) => k !== "id" && k !== "generation_id" && k !== "created_at")
                  .map(([k, v]) => (
                    <tr key={k}>
                      <td className="pr-3 py-0.5 text-gray-500">{k}</td>
                      <td className="py-0.5">{String(v)}</td>
                    </tr>
                  ))}
              </table>
            </div>
          )}

          {full && full.pairs.length > 0 && (
            <div className="mb-6">
              <h2 className="text-sm mb-2">{t("generate", "evalPairsHeading")}</h2>
              {full.pairs.map((p, i) => (
                <div key={p.id} className="mb-2 px-3 py-2 bg-gray-50 border border-gray-200 text-xs">
                  <strong>Q{i + 1}:</strong> {p.query}<br />
                  <span className="text-gray-600">A: {p.expected_answer}</span>
                </div>
              ))}
            </div>
          )}

          {latestGen.status === "done" && (
            <form action={triggerApprove}>
              <input type="hidden" name="generation_id" value={latestGen.id} />
              <button
                type="submit"
                className="bg-green-700 text-white border-0 px-6 py-2.5 cursor-pointer text-sm"
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
