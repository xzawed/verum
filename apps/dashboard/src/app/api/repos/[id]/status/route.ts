import { getRepoStatus, getWorkerAlive } from "@/lib/db/queries";
import { getAuthUserId } from "@/lib/api/handlers";

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const uid = await getAuthUserId();
  if (!uid) {
    return new Response("unauthorized", { status: 401 });
  }

  const { id } = await params;
  const status = await getRepoStatus(uid, id);
  if (!status) {
    return new Response("not found", { status: 404 });
  }

  const workerAlive = await getWorkerAlive();
  return Response.json(
    { status, workerAlive },
    { headers: { "Cache-Control": "no-store" } },
  );
}
