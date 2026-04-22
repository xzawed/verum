import { auth } from "@/auth";
import { getDeployment } from "@/lib/db/queries";

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const session = await auth();
  if (!session?.user) return new Response("unauthorized", { status: 401 });
  const uid = String((session.user as Record<string, unknown>).id ?? "");
  if (!uid) return new Response("unauthorized", { status: 401 });

  const { id } = await params;
  const deployment = await getDeployment(uid, id);
  if (!deployment) return new Response("not found", { status: 404 });

  return Response.json(deployment, { headers: { "Cache-Control": "no-store" } });
}
