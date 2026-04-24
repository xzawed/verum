import { z } from "zod";
import { enqueueGenerate } from "@/lib/db/jobs";
import { getInference } from "@/lib/db/queries";
import { getAuthUserId } from "@/lib/api/handlers";
import { checkRateLimit } from "@/lib/rateLimit";

const GenerateSchema = z.object({
  inference_id: z.string().uuid("inference_id must be a valid UUID"),
});

export async function POST(req: Request) {
  const uid = await getAuthUserId();
  if (!uid) return new Response("unauthorized", { status: 401 });
  const rateLimitResponse = checkRateLimit(uid, 20);
  if (rateLimitResponse) return rateLimitResponse;

  const parsed = GenerateSchema.safeParse(await req.json());
  if (!parsed.success) {
    return Response.json({ error: parsed.error.flatten() }, { status: 400 });
  }
  const { inference_id: inferenceId } = parsed.data;

  const inference = await getInference(uid, inferenceId);
  if (!inference) return new Response("not found", { status: 404 });

  const { generationId, jobId } = await enqueueGenerate({
    userId: uid,
    inferenceId,
  });

  return Response.json({ generation_id: generationId, job_id: jobId }, { status: 202 });
}
