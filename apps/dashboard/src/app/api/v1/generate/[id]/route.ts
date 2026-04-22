import { auth } from "@/auth";
import { getGenerationFull } from "@/lib/db/queries";

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const session = await auth();
  if (!session?.user) return new Response("unauthorized", { status: 401 });
  const uid = String((session.user as Record<string, unknown>).id ?? "");
  if (!uid) return new Response("unauthorized", { status: 401 });

  const { id } = await params;
  const data = await getGenerationFull(uid, id);
  if (!data) return new Response("not found", { status: 404 });

  return Response.json(data, { headers: { "Cache-Control": "no-store" } });
}
