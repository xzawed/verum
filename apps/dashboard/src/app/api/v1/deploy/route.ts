import { enqueueDeployment } from "@/lib/db/jobs";
import { getGeneration } from "@/lib/db/queries";
import { getAuthUserId } from "@/lib/api/handlers";

export async function POST(req: Request) {
  const uid = await getAuthUserId();
  if (!uid) return new Response("unauthorized", { status: 401 });

  const raw = await req.json() as unknown;
  const generationId =
    raw !== null &&
    typeof raw === "object" &&
    "generation_id" in raw &&
    typeof (raw as Record<string, unknown>).generation_id === "string"
      ? (raw as Record<string, unknown>).generation_id as string
      : "";
  if (!generationId) return new Response("generation_id required", { status: 400 });

  const gen = await getGeneration(uid, generationId);
  if (!gen) return new Response("not found", { status: 404 });
  if (gen.status !== "approved") return new Response("generation not approved", { status: 409 });

  const jobId = await enqueueDeployment({ userId: uid, generationId });
  return Response.json({ job_id: jobId }, { status: 202 });
}
