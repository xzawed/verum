import { listRailwayServices } from "@/lib/railway";
import { getAuthUserId } from "@/lib/api/handlers";

export async function GET(req: Request): Promise<Response> {
  const userId = await getAuthUserId();
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
