import { auth } from "@/auth";
import { listRailwayServices } from "@/lib/railway";

export async function GET(req: Request): Promise<Response> {
  const session = await auth();
  const user = session?.user as Record<string, unknown> | undefined;
  const userId = user?.id as string | undefined;
  if (!userId) return new Response("unauthorized", { status: 401 });

  const { searchParams } = new URL(req.url);
  const token = searchParams.get("token");
  if (!token) {
    return Response.json({ error: "token query parameter is required" }, { status: 400 });
  }

  try {
    const services = await listRailwayServices(token);
    return Response.json({ services });
  } catch {
    return Response.json({ error: "failed to fetch Railway services" }, { status: 502 });
  }
}
