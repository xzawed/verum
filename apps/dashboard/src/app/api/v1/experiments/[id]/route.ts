import { getExperiment } from "@/lib/db/queries";
import { getAuthUserId } from "@/lib/api/handlers";

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const userId = await getAuthUserId();
  if (!userId) return new Response("unauthorized", { status: 401 });
  const experiment = await getExperiment(userId, id);

  if (!experiment) return new Response("not found", { status: 404 });

  return Response.json(experiment, { headers: { "Cache-Control": "no-store" } });
}
