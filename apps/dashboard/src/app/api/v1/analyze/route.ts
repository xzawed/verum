import { enqueueAnalyze } from "@/lib/db/jobs";
import { getRepo } from "@/lib/db/queries";
import { getAuthUserId } from "@/lib/api/handlers";
import { checkRateLimit } from "@/lib/rateLimit";

export async function POST(req: Request) {
  const uid = await getAuthUserId();
  if (!uid) return new Response("unauthorized", { status: 401 });
  const rateLimitResponse = checkRateLimit(uid, 20);
  if (rateLimitResponse) return rateLimitResponse;

  const body = await req.json() as { repo_id: string; branch?: string };
  if (!body.repo_id) return new Response("repo_id required", { status: 400 });

  const repo = await getRepo(uid, body.repo_id);
  if (!repo) return new Response("not found", { status: 404 });

  const analysis = await enqueueAnalyze({
    userId: uid,
    repoId: repo.id,
    repoUrl: repo.github_url,
    branch: body.branch ?? repo.default_branch,
  });

  return Response.json({ job_id: analysis.id }, { status: 202 });
}
