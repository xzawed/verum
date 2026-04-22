import { auth } from "@/auth";
import { approveGeneration } from "@/lib/db/jobs";

export async function PATCH(
  _req: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const session = await auth();
  if (!session?.user) return new Response("unauthorized", { status: 401 });
  const uid = String((session.user as Record<string, unknown>).id ?? "");
  if (!uid) return new Response("unauthorized", { status: 401 });

  const { id } = await params;
  const ok = await approveGeneration(uid, id);
  if (!ok) return new Response("not found", { status: 404 });

  return Response.json({ status: "approved" });
}
