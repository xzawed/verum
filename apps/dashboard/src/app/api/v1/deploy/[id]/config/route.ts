import { db } from "@/lib/db/client";
import { deployments } from "@/lib/db/schema";
import { getVariantPrompt } from "@/lib/db/queries";
import { eq } from "drizzle-orm";

export async function GET(
  req: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const apiKey =
    req.headers.get("x-verum-api-key") ??
    req.headers.get("authorization")?.replace("Bearer ", "");
  if (!apiKey || apiKey !== process.env.VERUM_API_KEY) {
    return new Response("unauthorized", { status: 401 });
  }

  const { id } = await params;
  const rows = await db
    .select()
    .from(deployments)
    .where(eq(deployments.id, id))
    .limit(1);
  const deployment = rows[0];
  if (!deployment) return new Response("not found", { status: 404 });

  const split = deployment.traffic_split as { baseline: number; variant: number };
  const variantPrompt = await getVariantPrompt(id);

  return Response.json(
    {
      deployment_id: id,
      status: deployment.status,
      traffic_split: split.variant,
      variant_prompt: variantPrompt,
    },
    { headers: { "Cache-Control": "no-store" } },
  );
}
