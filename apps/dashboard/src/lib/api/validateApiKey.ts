import { createHash, timingSafeEqual } from "crypto";
import { db } from "@/lib/db/client";
import { deployments } from "@/lib/db/schema";
import { eq } from "drizzle-orm";

export async function validateApiKey(rawKey: string): Promise<string | null> {
  // Returns deployment_id if valid, null if invalid
  if (!rawKey || rawKey.length < 40) return null;
  const incomingHash = createHash("sha256").update(rawKey).digest("hex");
  const rows = await db
    .select({ id: deployments.id, apiKeyHash: deployments.apiKeyHash })
    .from(deployments)
    .where(eq(deployments.apiKeyHash, incomingHash))
    .limit(1);

  const row = rows[0];
  if (!row) return null;

  // Constant-time comparison to prevent timing attacks
  const storedHashBuf = Buffer.from(row.apiKeyHash, "hex");
  const incomingHashBuf = Buffer.from(incomingHash, "hex");
  if (
    storedHashBuf.byteLength !== incomingHashBuf.byteLength ||
    !timingSafeEqual(storedHashBuf, incomingHashBuf)
  ) {
    return null;
  }

  return row.id;
}
