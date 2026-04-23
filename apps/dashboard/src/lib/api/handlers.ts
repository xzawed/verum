import { auth } from "@/auth";

export async function getAuthUserId(): Promise<string | null> {
  const session = await auth();
  if (!session?.user) return null;
  const uid = String((session.user as Record<string, unknown>).id ?? "");
  return uid || null;
}

export function createGetByIdHandler<T>(
  queryFn: (userId: string, id: string) => Promise<T | null>
): (_req: Request, ctx: { params: Promise<{ id: string }> }) => Promise<Response> {
  return async (_req, { params }) => {
    const uid = await getAuthUserId();
    if (!uid) return new Response("unauthorized", { status: 401 });
    const { id } = await params;
    const data = await queryFn(uid, id);
    if (!data) return new Response("not found", { status: 404 });
    return Response.json(data, { headers: { "Cache-Control": "no-store" } });
  };
}
