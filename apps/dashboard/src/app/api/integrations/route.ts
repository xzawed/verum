import { NextRequest } from "next/server";
import { and, desc, eq } from "drizzle-orm";
import { z } from "zod";
import { auth } from "@/auth";
import { db } from "@/lib/db/client";
import { encrypt } from "@/lib/encrypt";
import { upsertRailwayVariables } from "@/lib/railway";
import { integrations, repos } from "@/lib/db/schema";

const CreateSchema = z.object({
  railway_token: z.string().min(1),
  project_id: z.string().min(1),
  service_id: z.string().min(1),
  environment_id: z.string().min(1),
  service_name: z.string().min(1),
  repo_id: z.string().uuid().optional(),
  inject_node_options: z.boolean().optional().default(false),
});

export async function GET(req: Request): Promise<Response> {
  const session = await auth();
  const user = session?.user as Record<string, unknown> | undefined;
  const userId = user?.id as string | undefined;
  if (!userId) return new Response("unauthorized", { status: 401 });

  const rows = await db
    .select({
      id: integrations.id,
      user_id: integrations.user_id,
      repo_id: integrations.repo_id,
      deployment_id: integrations.deployment_id,
      integration_type: integrations.integration_type,
      platform_project_id: integrations.platform_project_id,
      platform_service_id: integrations.platform_service_id,
      platform_environment_id: integrations.platform_environment_id,
      platform_service_name: integrations.platform_service_name,
      status: integrations.status,
      injected_vars: integrations.injected_vars,
      last_health_check: integrations.last_health_check,
      error: integrations.error,
      created_at: integrations.created_at,
      updated_at: integrations.updated_at,
    })
    .from(integrations)
    .where(eq(integrations.user_id, userId))
    .orderBy(desc(integrations.created_at));

  return Response.json({ integrations: rows });
}

export async function POST(req: Request): Promise<Response> {
  const session = await auth();
  const user = session?.user as Record<string, unknown> | undefined;
  const userId = user?.id as string | undefined;
  if (!userId) return new Response("unauthorized", { status: 401 });

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return Response.json({ error: "invalid JSON" }, { status: 400 });
  }

  const parsed = CreateSchema.safeParse(body);
  if (!parsed.success) {
    return Response.json({ error: parsed.error.flatten() }, { status: 400 });
  }

  const {
    railway_token,
    project_id,
    service_id,
    environment_id,
    service_name,
    repo_id,
    inject_node_options,
  } = parsed.data;

  // If repo_id provided, verify ownership
  if (repo_id) {
    const repoRows = await db
      .select({ id: repos.id })
      .from(repos)
      .where(and(eq(repos.id, repo_id), eq(repos.owner_user_id, userId)))
      .limit(1);
    if (repoRows.length === 0) {
      return new Response("not found", { status: 404 });
    }
  }

  // Derive verumBase from forwarded headers (NextRequest-compatible)
  const nextReq = req as NextRequest;
  const proto =
    nextReq.headers.get("x-forwarded-proto") ??
    new URL(req.url).protocol.replace(/:$/, "");
  const host =
    nextReq.headers.get("x-forwarded-host") ??
    nextReq.headers.get("host") ??
    new URL(req.url).host;
  const verumBase = `${proto}://${host}`;

  // Build injected vars
  const injectedVars: Record<string, string> = {
    OTEL_EXPORTER_OTLP_ENDPOINT: `${verumBase}/api/v1/otlp/v1/traces`,
  };
  if (inject_node_options) {
    injectedVars["NODE_OPTIONS"] =
      "--require @opentelemetry/auto-instrumentations-node/register";
  }

  // Push to Railway
  try {
    await upsertRailwayVariables(
      railway_token,
      project_id,
      service_id,
      environment_id,
      injectedVars,
    );
  } catch {
    return Response.json({ error: "failed to set Railway variables" }, { status: 502 });
  }

  // Persist integration
  const encryptedToken = encrypt(railway_token);
  const [row] = await db
    .insert(integrations)
    .values({
      user_id: userId,
      repo_id: repo_id ?? null,
      integration_type: "railway",
      platform_project_id: project_id,
      platform_service_id: service_id,
      platform_environment_id: environment_id,
      platform_service_name: service_name,
      platform_token_encrypted: encryptedToken,
      status: "connected",
      injected_vars: injectedVars,
    })
    .returning({ id: integrations.id });

  return Response.json({ integration_id: String(row.id) }, { status: 201 });
}
