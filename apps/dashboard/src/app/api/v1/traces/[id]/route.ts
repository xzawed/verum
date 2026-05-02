import { auth } from "@/auth";
import { getTraceDetail } from "@/lib/db/queries";

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const session = await auth();
  if (!session?.user) return new Response("unauthorized", { status: 401 });

  const { id } = await params;
  const userId = String((session.user as Record<string, unknown>).id ?? "");
  if (!userId) return new Response("unauthorized", { status: 401 });
  const trace = await getTraceDetail(userId, id);
  if (!trace) return new Response("not found", { status: 404 });

  return Response.json(trace, { headers: { "Cache-Control": "no-store" } });
}
