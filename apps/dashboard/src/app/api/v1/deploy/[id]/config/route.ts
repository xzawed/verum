import { db } from "@/lib/db/client";
import { deployments, prompt_variants, rag_configs } from "@/lib/db/schema";
import { getVariantPrompt } from "@/lib/db/queries";
import { validateApiKey } from "@/lib/api/validateApiKey";
import { eq } from "drizzle-orm";

interface PromptVariantResponse {
  id: string;
  variant_type: string;
  content: string;
}

interface RagConfigResponse {
  chunking_strategy: string;
  chunk_size: number;
  chunk_overlap: number;
  top_k: number;
  hybrid_alpha: number;
}

export async function GET(
  req: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const rawKey =
    req.headers.get("x-verum-api-key") ??
    req.headers.get("authorization")?.replace("Bearer ", "") ??
    "";
  const keyResult = await validateApiKey(rawKey);
  if (!keyResult) {
    return new Response("unauthorized", { status: 401 });
  }

  const { id } = await params;

  // Ensure the API key belongs to this deployment (prevents UUID enumeration).
  if (keyResult.deploymentId !== id) {
    return new Response("forbidden", { status: 403 });
  }

  const rows = await db
    .select()
    .from(deployments)
    .where(eq(deployments.id, id))
    .limit(1);
  const deployment = rows[0];
  if (!deployment) return new Response("not found", { status: 404 });

  const split = deployment.traffic_split as { baseline: number; variant: number };
  const variantPrompt = await getVariantPrompt(id);

  // Fetch all prompt variants and RAG config in parallel.
  const [variantRows, ragRows] = await Promise.all([
    db
      .select({
        id: prompt_variants.id,
        variant_type: prompt_variants.variant_type,
        content: prompt_variants.content,
      })
      .from(prompt_variants)
      .where(eq(prompt_variants.generation_id, deployment.generation_id))
      .orderBy(prompt_variants.created_at),
    db
      .select({
        chunking_strategy: rag_configs.chunking_strategy,
        chunk_size: rag_configs.chunk_size,
        chunk_overlap: rag_configs.chunk_overlap,
        top_k: rag_configs.top_k,
        hybrid_alpha: rag_configs.hybrid_alpha,
      })
      .from(rag_configs)
      .where(eq(rag_configs.generation_id, deployment.generation_id))
      .limit(1),
  ]);

  const variants: PromptVariantResponse[] = variantRows.map((row) => ({
    id: row.id,
    variant_type: row.variant_type,
    content: row.content,
  }));

  const ragConfig: RagConfigResponse | null = ragRows[0] ?? null;

  return Response.json(
    {
      deployment_id: id,
      status: deployment.status,
      traffic_split: split.variant,
      variant_prompt: variantPrompt,
      prompt_variants: variants,
      rag_config: ragConfig,
    },
    { headers: { "Cache-Control": "no-store" } },
  );
}
