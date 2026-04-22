import { auth } from "@/auth";
import { enqueueAnalyze } from "@/lib/db/jobs";
import { getRepo } from "@/lib/db/queries";

export async function POST(req: Request) {
  const session = await auth();
  if (!session?.user) return new Response("unauthorized", { status: 401 });
  const uid = String((session.user as Record<string, unknown>).id ?? "");
  if (!uid) return new Response("unauthorized", { status: 401 });

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
