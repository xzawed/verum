import { updateDeploymentTraffic } from "@/lib/db/jobs";
import { getDeployment } from "@/lib/db/queries";
import { getAuthUserId } from "@/lib/api/handlers";

export async function PATCH(
  req: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const uid = await getAuthUserId();
  if (!uid) return new Response("unauthorized", { status: 401 });

  const { id } = await params;
  const deployment = await getDeployment(uid, id);
  if (!deployment) return new Response("not found", { status: 404 });

  const raw = await req.json() as unknown;
  const split =
    raw !== null &&
    typeof raw === "object" &&
    "split" in raw &&
    typeof (raw as Record<string, unknown>).split === "number"
      ? (raw as Record<string, unknown>).split as number
      : null;
  if (split === null || split < 0 || split > 1) {
    return new Response("split must be a number between 0 and 1", { status: 400 });
  }

  await updateDeploymentTraffic(uid, id, split);
  return Response.json({ ok: true });
}
