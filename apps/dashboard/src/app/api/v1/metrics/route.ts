import { auth } from "@/auth";
import { getDailyMetrics, getDeployment } from "@/lib/db/queries";

export async function GET(req: Request) {
  const session = await auth();
  if (!session?.user) return new Response("unauthorized", { status: 401 });

  const { searchParams } = new URL(req.url);
  const deploymentId = searchParams.get("deployment_id") ?? "";
  const days = Number(searchParams.get("days") ?? "7");

  if (!deploymentId) return new Response("deployment_id required", { status: 400 });

  const userId = String((session.user as Record<string, unknown>).id ?? "");
  if (!userId) return new Response("unauthorized", { status: 401 });
  const dep = await getDeployment(userId, deploymentId);
  if (!dep) return new Response("not found", { status: 404 });

  const daily = await getDailyMetrics(deploymentId, days);
  return Response.json({ daily }, { headers: { "Cache-Control": "no-store" } });
}
