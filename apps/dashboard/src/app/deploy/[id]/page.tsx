import { notFound, redirect } from "next/navigation";
import { auth } from "@/auth";
import { rollbackDeployment, updateDeploymentTraffic } from "@/lib/db/jobs";
import { getDeployment } from "@/lib/db/queries";
import { t } from "@/lib/i18n";

export default async function DeployPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const session = await auth();
  if (!session?.user) redirect("/login");
  const uid = String((session.user as Record<string, unknown>).id ?? "");
  if (!uid) redirect("/login");

  const { id } = await params;

  const deployment = await getDeployment(uid, id);
  if (!deployment) notFound();

  const split = deployment.traffic_split as { baseline: number; variant: number };
  const variantPct = Math.round((split.variant ?? 0) * 100);
  const errorRate =
    deployment.total_calls > 0
      ? ((deployment.error_count / deployment.total_calls) * 100).toFixed(2)
      : "0.00";

  async function triggerRollback() {
    "use server";
    const session = await auth();
    if (!session?.user) return;
    const uid = String((session.user as Record<string, unknown>).id ?? "");
    if (!uid) return;
    await rollbackDeployment(uid, id);
    redirect(`/deploy/${id}`);
  }

  async function setTraffic10() {
    "use server";
    const session = await auth();
    if (!session?.user) return;
    const uid = String((session.user as Record<string, unknown>).id ?? "");
    if (!uid) return;
    await updateDeploymentTraffic(uid, id, 0.1);
    redirect(`/deploy/${id}`);
  }

  async function setTraffic50() {
    "use server";
    const session = await auth();
    if (!session?.user) return;
    const uid = String((session.user as Record<string, unknown>).id ?? "");
    if (!uid) return;
    await updateDeploymentTraffic(uid, id, 0.5);
    redirect(`/deploy/${id}`);
  }

  async function setTraffic100() {
    "use server";
    const session = await auth();
    if (!session?.user) return;
    const uid = String((session.user as Record<string, unknown>).id ?? "");
    if (!uid) return;
    await updateDeploymentTraffic(uid, id, 1.0);
    redirect(`/deploy/${id}`);
  }

  return (
    <main className="max-w-3xl mx-auto mt-10 font-mono px-4">
      <h1 className="text-2xl mt-4 mb-1">DEPLOY — Canary Deployment</h1>

      <div className="flex gap-8 mb-6 mt-4">
        <div><strong>Status</strong><br />{deployment.status}</div>
        <div><strong>Variant traffic</strong><br />{variantPct}%</div>
        <div><strong>Total calls</strong><br />{deployment.total_calls}</div>
        <div><strong>Error rate</strong><br />{errorRate}%</div>
      </div>

      {deployment.status === "rolled_back" && (
        <div className="bg-red-50 border border-red-400 px-4 py-3 mb-4">
          <strong className="text-red-500">{t("deploy", "rolledBackLabel")}</strong> — {t("deploy", "rolledBackDesc")}
        </div>
      )}

      <div className="mb-6">
        <h2 className="text-sm mb-2">{t("deploy", "trafficSplitHeading")}</h2>
        <div className="flex gap-2">
          <form action={setTraffic10}>
            <button
              type="submit"
              className={`px-4 py-1.5 border border-gray-300 cursor-pointer text-sm ${variantPct === 10 ? "bg-black text-white" : "bg-white text-black"}`}
            >
              10%
            </button>
          </form>
          <form action={setTraffic50}>
            <button
              type="submit"
              className={`px-4 py-1.5 border border-gray-300 cursor-pointer text-sm ${variantPct === 50 ? "bg-black text-white" : "bg-white text-black"}`}
            >
              50%
            </button>
          </form>
          <form action={setTraffic100}>
            <button
              type="submit"
              className={`px-4 py-1.5 border border-gray-300 cursor-pointer text-sm ${variantPct === 100 ? "bg-black text-white" : "bg-white text-black"}`}
            >
              100%
            </button>
          </form>
        </div>
        <p className="text-xs text-gray-400 mt-2">
          {t("deploy", "trafficRefreshHint")}
        </p>
      </div>

      {deployment.status !== "rolled_back" && (
        <form action={triggerRollback}>
          <button
            type="submit"
            className="bg-red-500 text-white border-0 px-[18px] py-2 cursor-pointer text-sm"
          >
            {t("deploy", "rollbackButton")}
          </button>
        </form>
      )}
    </main>
  );
}
