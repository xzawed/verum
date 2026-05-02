import { rollbackDeployment } from "@/lib/db/jobs";
import { getDeployment } from "@/lib/db/queries";
import { checkRateLimit } from "@/lib/rateLimit";
import { getAuthUserId } from "@/lib/api/handlers";

export async function POST(
  _req: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const uid = await getAuthUserId();
  if (!uid) return new Response("unauthorized", { status: 401 });
  const rateLimitResponse = await checkRateLimit(uid, 20);
  if (rateLimitResponse) return rateLimitResponse;

  const { id } = await params;
  const deployment = await getDeployment(uid, id);
  if (!deployment) return new Response("not found", { status: 404 });

  await rollbackDeployment(uid, id);
  return Response.json({ status: "rolled_back" });
}
