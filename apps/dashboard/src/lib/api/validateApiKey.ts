import { createHash } from "crypto";
import { db } from "@/lib/db/client";
import { deployments } from "@/lib/db/schema";
import { eq } from "drizzle-orm";

export async function validateApiKey(rawKey: string): Promise<string | null> {
  // Returns deployment_id if valid, null if invalid
  if (!rawKey || rawKey.length < 10) return null;
  const hash = createHash("sha256").update(rawKey).digest("hex");
  const rows = await db
    .select({ id: deployments.id })
    .from(deployments)
    .where(eq(deployments.apiKeyHash, hash))
    .limit(1);
  return rows[0]?.id ?? null;
}
