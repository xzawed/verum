import { z } from "zod";
import { enqueueInfer } from "@/lib/db/jobs";
import { getAnalysis } from "@/lib/db/queries";
import { getAuthUserId } from "@/lib/api/handlers";
import { checkRateLimit } from "@/lib/rateLimit";

const InferSchema = z.object({
  analysis_id: z.string().uuid("analysis_id must be a valid UUID"),
  repo_id: z.string().uuid("repo_id must be a valid UUID"),
});

export async function POST(req: Request) {
  const uid = await getAuthUserId();
  if (!uid) return new Response("unauthorized", { status: 401 });
  const rateLimitResponse = await checkRateLimit(uid, 20);
  if (rateLimitResponse) return rateLimitResponse;

  const parsed = InferSchema.safeParse(await req.json());
  if (!parsed.success) {
    return Response.json({ error: parsed.error.flatten() }, { status: 400 });
  }
  const body = parsed.data;

  const analysis = await getAnalysis(uid, body.analysis_id);
  if (!analysis) return new Response("not found", { status: 404 });

  const inference = await enqueueInfer({
    userId: uid,
    repoId: body.repo_id,
    analysisId: body.analysis_id,
  });

  return Response.json({ job_id: inference.id }, { status: 202 });
}
