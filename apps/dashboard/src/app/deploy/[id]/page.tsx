import { notFound, redirect } from "next/navigation";
import { auth } from "@/auth";
import { rollbackDeployment, updateDeploymentTraffic } from "@/lib/db/jobs";
import { getDeployment } from "@/lib/db/queries";

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
    await rollbackDeployment(id);
    redirect(`/deploy/${id}`);
  }

  async function setTraffic10() {
    "use server";
    await updateDeploymentTraffic(id, 0.1);
    redirect(`/deploy/${id}`);
  }

  async function setTraffic50() {
    "use server";
    await updateDeploymentTraffic(id, 0.5);
    redirect(`/deploy/${id}`);
  }

  async function setTraffic100() {
    "use server";
    await updateDeploymentTraffic(id, 1.0);
    redirect(`/deploy/${id}`);
  }

  return (
    <main style={{ maxWidth: 720, margin: "40px auto", fontFamily: "monospace", padding: "0 16px" }}>
      <h1 style={{ fontSize: 22, margin: "16px 0 4px" }}>DEPLOY — Canary Deployment</h1>

      <div style={{ display: "flex", gap: 32, marginBottom: 24, marginTop: 16 }}>
        <div><strong>Status</strong><br />{deployment.status}</div>
        <div><strong>Variant traffic</strong><br />{variantPct}%</div>
        <div><strong>Total calls</strong><br />{deployment.total_calls}</div>
        <div><strong>Error rate</strong><br />{errorRate}%</div>
      </div>

      {deployment.status === "rolled_back" && (
        <div style={{ background: "#fef2f2", border: "1px solid #ef4444", padding: "12px 16px", marginBottom: 16 }}>
          <strong style={{ color: "#ef4444" }}>롤백됨</strong> — 기본 프롬프트로 복원되었습니다.
        </div>
      )}

      <div style={{ marginBottom: 24 }}>
        <h2 style={{ fontSize: 14, marginBottom: 8 }}>트래픽 조정</h2>
        <div style={{ display: "flex", gap: 8 }}>
          <form action={setTraffic10}>
            <button
              type="submit"
              style={{
                padding: "6px 16px",
                border: "1px solid #ddd",
                background: variantPct === 10 ? "#000" : "#fff",
                color: variantPct === 10 ? "#fff" : "#000",
                cursor: "pointer",
                fontSize: 13,
              }}
            >
              10%
            </button>
          </form>
          <form action={setTraffic50}>
            <button
              type="submit"
              style={{
                padding: "6px 16px",
                border: "1px solid #ddd",
                background: variantPct === 50 ? "#000" : "#fff",
                color: variantPct === 50 ? "#fff" : "#000",
                cursor: "pointer",
                fontSize: 13,
              }}
            >
              50%
            </button>
          </form>
          <form action={setTraffic100}>
            <button
              type="submit"
              style={{
                padding: "6px 16px",
                border: "1px solid #ddd",
                background: variantPct === 100 ? "#000" : "#fff",
                color: variantPct === 100 ? "#fff" : "#000",
                cursor: "pointer",
                fontSize: 13,
              }}
            >
              100%
            </button>
          </form>
        </div>
        <p style={{ fontSize: 11, color: "#888", marginTop: 8 }}>
          트래픽 변경 후 페이지를 새로고침하면 반영됩니다.
        </p>
      </div>

      {deployment.status !== "rolled_back" && (
        <form action={triggerRollback}>
          <button
            type="submit"
            style={{
              background: "#ef4444",
              color: "#fff",
              border: "none",
              padding: "8px 18px",
              cursor: "pointer",
              fontSize: 13,
            }}
          >
            롤백
          </button>
        </form>
      )}
    </main>
  );
}
