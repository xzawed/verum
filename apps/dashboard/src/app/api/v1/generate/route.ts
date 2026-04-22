import { auth } from "@/auth";
import { enqueueGenerate } from "@/lib/db/jobs";
import { getInference } from "@/lib/db/queries";

export async function POST(req: Request) {
  const session = await auth();
  if (!session?.user) return new Response("unauthorized", { status: 401 });
  const uid = String((session.user as Record<string, unknown>).id ?? "");
  if (!uid) return new Response("unauthorized", { status: 401 });

  const body = await req.json() as { inference_id: string };
  if (!body.inference_id) return new Response("inference_id required", { status: 400 });

  const inference = await getInference(uid, body.inference_id);
  if (!inference) return new Response("not found", { status: 404 });

  const { generationId, jobId } = await enqueueGenerate({
    userId: uid,
    inferenceId: body.inference_id,
  });

  return Response.json({ generation_id: generationId, job_id: jobId }, { status: 202 });
}
