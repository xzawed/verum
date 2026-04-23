import { createHash } from "crypto";
import { findDeploymentByApiKey } from "@/lib/db/deploys";

export type ApiKeyResult = { deploymentId: string; userId: string };

export async function validateApiKey(rawKey: string): Promise<ApiKeyResult | null> {
  if (!rawKey || rawKey.length < 40) return null;
  const hash = createHash("sha256").update(rawKey).digest("hex");
  const row = await findDeploymentByApiKey(hash);
  if (!row) return null;
  return { deploymentId: row.id, userId: row.userId };
}
