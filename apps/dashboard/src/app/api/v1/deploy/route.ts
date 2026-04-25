import { z } from "zod";
import { enqueueDeployment } from "@/lib/db/jobs";
import { getGeneration } from "@/lib/db/queries";
import { getAuthUserId } from "@/lib/api/handlers";
import { checkRateLimit } from "@/lib/rateLimit";

const DeploySchema = z.object({
  generation_id: z.string().uuid("generation_id must be a valid UUID"),
});

export async function POST(req: Request) {
  const uid = await getAuthUserId();
  if (!uid) return new Response("unauthorized", { status: 401 });
  const rateLimitResponse = await checkRateLimit(uid, 20);
  if (rateLimitResponse) return rateLimitResponse;

  const parsed = DeploySchema.safeParse(await req.json());
  if (!parsed.success) {
    return Response.json({ error: parsed.error.flatten() }, { status: 400 });
  }
  const { generation_id: generationId } = parsed.data;

  const gen = await getGeneration(uid, generationId);
  if (!gen) return new Response("not found", { status: 404 });
  if (gen.status !== "approved") return new Response("generation not approved", { status: 409 });

  const jobId = await enqueueDeployment({ userId: uid, generationId });
  return Response.json({ job_id: jobId }, { status: 202 });
}
