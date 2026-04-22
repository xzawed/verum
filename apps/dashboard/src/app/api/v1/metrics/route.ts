import { auth } from "@/auth";
import { getDailyMetrics } from "@/lib/db/queries";

export async function GET(req: Request) {
  const session = await auth();
  if (!session?.user) return new Response("unauthorized", { status: 401 });

  const { searchParams } = new URL(req.url);
  const deploymentId = searchParams.get("deployment_id") ?? "";
  const days = Number(searchParams.get("days") ?? "7");

  if (!deploymentId) return new Response("deployment_id required", { status: 400 });

  const daily = await getDailyMetrics(deploymentId, days);
  return Response.json({ daily }, { headers: { "Cache-Control": "no-store" } });
}
