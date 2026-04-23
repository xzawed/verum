import { auth } from "@/auth";
import { getDeployment, getExperiments } from "@/lib/db/queries";

export async function GET(req: Request) {
  const session = await auth();
  if (!session?.user) return new Response("unauthorized", { status: 401 });

  const { searchParams } = new URL(req.url);
  const deploymentId = searchParams.get("deployment_id") ?? "";
  if (!deploymentId) return new Response("deployment_id required", { status: 400 });

  const userId = session.user.id as string;
  const dep = await getDeployment(userId, deploymentId);
  if (!dep) return new Response("not found", { status: 404 });

  const allExperiments = await getExperiments(userId, deploymentId);
  const current = allExperiments.find((e) => e.status === "running") ?? null;

  return Response.json(
    { experiments: allExperiments, current_experiment: current },
    { headers: { "Cache-Control": "no-store" } },
  );
}
