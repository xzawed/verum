import { eq } from "drizzle-orm";
import { db } from "./client";
import { deployments, generations, inferences, repos } from "./schema";

/**
 * Look up a deployment by the SHA-256 hash of its API key.
 *
 * Used by SDK-facing API routes to authenticate inbound requests.
 * The raw API key is hashed by the caller before passing to this function.
 *
 * @param apiKeyHash - hex-encoded SHA-256 digest of the raw API key
 * @returns deployment id and owner user id, or null if not found
 */
export async function findDeploymentByApiKey(
  apiKeyHash: string
): Promise<{ id: string; userId: string } | null> {
  const rows = await db
    .select({ id: deployments.id, userId: repos.owner_user_id })
    .from(deployments)
    .innerJoin(generations, eq(deployments.generation_id, generations.id))
    .innerJoin(inferences, eq(generations.inference_id, inferences.id))
    .innerJoin(repos, eq(inferences.repo_id, repos.id))
    .where(eq(deployments.apiKeyHash, apiKeyHash))
    .limit(1);
  if (!rows[0]) return null;
  return rows[0];
}
