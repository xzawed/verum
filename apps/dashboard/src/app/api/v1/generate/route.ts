import { enqueueGenerate } from "@/lib/db/jobs";
import { getInference } from "@/lib/db/queries";
import { getAuthUserId } from "@/lib/api/handlers";
import { checkRateLimit } from "@/lib/rateLimit";

export async function POST(req: Request) {
  const uid = await getAuthUserId();
  if (!uid) return new Response("unauthorized", { status: 401 });
  const rateLimitResponse = checkRateLimit(uid, 20);
  if (rateLimitResponse) return rateLimitResponse;

  const raw = await req.json() as unknown;
  const inferenceId =
    raw !== null &&
    typeof raw === "object" &&
    "inference_id" in raw &&
    typeof (raw as Record<string, unknown>).inference_id === "string"
      ? (raw as Record<string, unknown>).inference_id as string
      : "";
  if (!inferenceId) return new Response("inference_id required", { status: 400 });

  const inference = await getInference(uid, inferenceId);
  if (!inference) return new Response("not found", { status: 404 });

  const { generationId, jobId } = await enqueueGenerate({
    userId: uid,
    inferenceId,
  });

  return Response.json({ generation_id: generationId, job_id: jobId }, { status: 202 });
}
