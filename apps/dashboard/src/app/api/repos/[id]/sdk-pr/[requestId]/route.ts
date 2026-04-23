import { NextRequest } from "next/server";
import { getAuthUserId } from "@/lib/api/handlers";
import { getSdkPrRequest } from "@/lib/db/queries";

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string; requestId: string }> },
) {
  const userId = await getAuthUserId();
  if (!userId) return new Response("unauthorized", { status: 401 });
  const { id, requestId } = await params;
  const request = await getSdkPrRequest(userId, requestId);
  if (!request) return new Response("not found", { status: 404 });
  if (request.repo_id !== id) return new Response("not found", { status: 404 });
  return Response.json(request);
}
