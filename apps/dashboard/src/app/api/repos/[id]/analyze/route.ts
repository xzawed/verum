import { getAuthUserId } from "@/lib/api/handlers";
import { enqueueAnalyze } from "@/lib/db/jobs";
import { getRepo } from "@/lib/db/queries";

export async function POST(
  _req: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const uid = await getAuthUserId();
  if (!uid) return new Response("unauthorized", { status: 401 });
  const { id } = await params;
  const repo = await getRepo(uid, id);
  if (!repo) return new Response("not found", { status: 404 });
  const analysis = await enqueueAnalyze({
    userId: uid,
    repoId: repo.id,
    repoUrl: repo.github_url,
    branch: repo.default_branch,
  });
  return Response.json({ job_id: analysis.id }, { status: 202 });
}
