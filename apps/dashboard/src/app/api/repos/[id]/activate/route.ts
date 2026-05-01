import { createHash, randomBytes } from "crypto";
import { NextRequest } from "next/server";
import { and, desc, eq, or } from "drizzle-orm";
import { auth } from "@/auth";
import { db } from "@/lib/db/client";
import { deployments, experiments, generations, inferences, repos } from "@/lib/db/schema";

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const session = await auth();
  const user = session?.user as Record<string, unknown> | undefined;
  const userId = user?.id as string | undefined;
  if (!userId) return new Response("unauthorized", { status: 401 });

  const { id: repoId } = await params;

  const ownerRows = await db
    .select({ id: repos.id })
    .from(repos)
    .where(and(eq(repos.id, repoId), eq(repos.owner_user_id, userId)))
    .limit(1);
  if (ownerRows.length === 0) {
    return new Response("not found", { status: 404 });
  }

  // Find latest generation in 'done' or 'approved' state via inference chain
  const genRows = await db
    .select({ id: generations.id })
    .from(generations)
    .innerJoin(inferences, eq(generations.inference_id, inferences.id))
    .where(
      and(
        eq(inferences.repo_id, repoId),
        or(eq(generations.status, "done"), eq(generations.status, "approved")),
      ),
    )
    .orderBy(desc(generations.created_at))
    .limit(1);

  if (genRows.length === 0) {
    return new Response("no generation ready for activation", { status: 422 });
  }

  const generationId = String(genRows[0].id);

  const existingDep = await db
    .select({ id: deployments.id })
    .from(deployments)
    .where(eq(deployments.generation_id, generationId))
    .limit(1);

  if (existingDep.length > 0) {
    return Response.json(
      { error: "deployment already exists", deployment_id: String(existingDep[0].id) },
      { status: 409 },
    );
  }

  const token = randomBytes(32).toString("hex");
  const apiKey = `vk_${token}`;
  const apiKeyHash = createHash("sha256").update(apiKey).digest("hex");

  const [dep] = await db
    .insert(deployments)
    .values({ generation_id: generationId, status: "active", apiKeyHash })
    .returning({ id: deployments.id });

  await db.insert(experiments).values({
    deployment_id: String(dep.id),
    baseline_variant: "original",
    challenger_variant: "variant",
    status: "running",
  });

  const proto = req.headers.get("x-forwarded-proto") ?? new URL(req.url).protocol.replace(/:$/, "");
  const host = req.headers.get("x-forwarded-host") ?? req.headers.get("host") ?? new URL(req.url).host;
  const verumApiUrl = `${proto}://${host}`;

  return Response.json(
    { deployment_id: String(dep.id), api_key: apiKey, verum_api_url: verumApiUrl },
    { status: 201 },
  );
}
