import { enqueueInfer } from "@/lib/db/jobs";
import { getAnalysis } from "@/lib/db/queries";
import { getAuthUserId } from "@/lib/api/handlers";

export async function POST(req: Request) {
  const uid = await getAuthUserId();
  if (!uid) return new Response("unauthorized", { status: 401 });

  const body = await req.json() as { analysis_id: string; repo_id: string };
  if (!body.analysis_id || !body.repo_id) {
    return new Response("analysis_id and repo_id required", { status: 400 });
  }

  const analysis = await getAnalysis(uid, body.analysis_id);
  if (!analysis) return new Response("not found", { status: 404 });

  const inference = await enqueueInfer({
    userId: uid,
    repoId: body.repo_id,
    analysisId: body.analysis_id,
  });

  return Response.json({ job_id: inference.id }, { status: 202 });
}
