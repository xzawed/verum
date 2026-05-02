import { and, eq } from "drizzle-orm";
import { auth } from "@/auth";
import { db } from "@/lib/db/client";
import { decrypt } from "@/lib/encrypt";
import { deleteRailwayVariables } from "@/lib/railway";
import { integrations } from "@/lib/db/schema";

export async function POST(
  _req: Request,
  { params }: { params: Promise<{ id: string }> },
): Promise<Response> {
  const session = await auth();
  const user = session?.user as Record<string, unknown> | undefined;
  const userId = user?.id as string | undefined;
  if (!userId) return new Response("unauthorized", { status: 401 });

  const { id } = await params;

  const rows = await db
    .select({
      id: integrations.id,
      platform_token_encrypted: integrations.platform_token_encrypted,
      platform_project_id: integrations.platform_project_id,
      platform_service_id: integrations.platform_service_id,
      platform_environment_id: integrations.platform_environment_id,
      injected_vars: integrations.injected_vars,
    })
    .from(integrations)
    .where(and(eq(integrations.id, id), eq(integrations.user_id, userId)))
    .limit(1);

  if (rows.length === 0) {
    return new Response("not found", { status: 404 });
  }

  const integration = rows[0];

  // Best-effort cleanup: delete injected variables from Railway
  if (
    integration.platform_token_encrypted &&
    integration.platform_project_id &&
    integration.platform_service_id &&
    integration.platform_environment_id
  ) {
    try {
      const token = decrypt(integration.platform_token_encrypted);
      const varNames = Object.keys(
        (integration.injected_vars as Record<string, unknown>) ?? {},
      );
      if (varNames.length > 0) {
        await deleteRailwayVariables(
          token,
          integration.platform_project_id,
          integration.platform_service_id,
          integration.platform_environment_id,
          varNames,
        );
      }
    } catch {
      // Ignore errors — user can clean up manually
    }
  }

  // Mark as disconnected
  await db
    .update(integrations)
    .set({ status: "disconnected", updated_at: new Date() })
    .where(eq(integrations.id, id));

  return Response.json({ success: true });
}
