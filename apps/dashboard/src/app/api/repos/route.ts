import { getAuthUserId } from "@/lib/api/handlers";
import { checkRateLimit } from "@/lib/rateLimit";
import { createRepo } from "@/lib/db/jobs";
import { getRepos } from "@/lib/db/queries";

export async function GET() {
  const uid = await getAuthUserId();
  if (!uid) return new Response("unauthorized", { status: 401 });
  const data = await getRepos(uid);
  return Response.json(data, { headers: { "Cache-Control": "no-store" } });
}

export async function POST(req: Request) {
  const uid = await getAuthUserId();
  if (!uid) return new Response("unauthorized", { status: 401 });
  const rateLimitResponse = checkRateLimit(uid, 20);
  if (rateLimitResponse) return rateLimitResponse;
  const body = (await req.json()) as { repo_url?: string; branch?: string };
  if (!body.repo_url) return new Response("repo_url required", { status: 400 });
  const repo = await createRepo(uid, body.repo_url, body.branch);
  return Response.json(repo, { status: 201, headers: { "Cache-Control": "no-store" } });
}
