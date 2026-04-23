import { eq } from "drizzle-orm";
import { db } from "./client";
import { deployments } from "./schema";

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
    .select({ id: deployments.id })
    .from(deployments)
    .where(eq(deployments.apiKeyHash, apiKeyHash))
    .limit(1);
  if (!rows[0]) return null;
  return { id: rows[0].id, userId: rows[0].id };
}
