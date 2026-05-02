import { approveGeneration } from "@/lib/db/jobs";
import { getAuthUserId } from "@/lib/api/handlers";

export async function PATCH(
  _req: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const uid = await getAuthUserId();
  if (!uid) return new Response("unauthorized", { status: 401 });

  const { id } = await params;
  const ok = await approveGeneration(uid, id);
  if (!ok) return new Response("not found", { status: 404 });

  return Response.json({ status: "approved" });
}
