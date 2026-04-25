import { auth } from "@/auth";
import { checkRateLimitDual, getClientIp } from "@/lib/rateLimit";

export async function getAuthUserId(): Promise<string | null> {
  const session = await auth();
  if (!session?.user) return null;
  const uid = String((session.user as Record<string, unknown>).id ?? "");
  return uid || null;
}

export function createGetByIdHandler<T>(
  queryFn: (userId: string, id: string) => Promise<T | null>
): (req: Request, ctx: { params: Promise<{ id: string }> }) => Promise<Response> {
  return async (req, { params }) => {
    const uid = await getAuthUserId();
    if (!uid) return new Response("unauthorized", { status: 401 });

    // 60 reads/min per user; 200/min per IP (covers multiple users behind NAT).
    const ip = getClientIp(req);
    const limited = checkRateLimitDual(uid, 60, ip, 200);
    if (limited) return limited;

    const { id } = await params;
    const data = await queryFn(uid, id);
    if (!data) return new Response("not found", { status: 404 });
    return Response.json(data, { headers: { "Cache-Control": "no-store" } });
  };
}
