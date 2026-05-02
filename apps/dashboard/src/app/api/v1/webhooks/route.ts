import { randomBytes } from "crypto";
import { db } from "@/lib/db/client";
import { webhook_subscriptions } from "@/lib/db/schema";
import { and, eq } from "drizzle-orm";
import { getAuthUserId } from "@/lib/api/handlers";

export async function GET(req: Request) {
  const userId = await getAuthUserId();
  if (!userId) return new Response("unauthorized", { status: 401 });

  const { searchParams } = new URL(req.url);
  const deploymentId = searchParams.get("deployment_id");

  const conditions = [eq(webhook_subscriptions.user_id, userId)];
  if (deploymentId) {
    conditions.push(eq(webhook_subscriptions.deployment_id, deploymentId));
  }

  const rows = await db
    .select({
      id: webhook_subscriptions.id,
      deployment_id: webhook_subscriptions.deployment_id,
      url: webhook_subscriptions.url,
      events: webhook_subscriptions.events,
      is_active: webhook_subscriptions.is_active,
      created_at: webhook_subscriptions.created_at,
    })
    .from(webhook_subscriptions)
    .where(and(...conditions));

  return Response.json({ webhooks: rows });
}

export async function POST(req: Request) {
  const userId = await getAuthUserId();
  if (!userId) return new Response("unauthorized", { status: 401 });

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return new Response("invalid JSON", { status: 400 });
  }

  const { url, events, deployment_id } = body as {
    url?: unknown;
    events?: unknown;
    deployment_id?: unknown;
  };

  if (typeof url !== "string" || !url.startsWith("https://")) {
    return new Response("url must be an https:// URL", { status: 400 });
  }

  const eventList: string[] = Array.isArray(events)
    ? (events as string[])
    : ["experiment.winner_promoted"];
  const validEvents = new Set(["experiment.winner_promoted", "experiment.completed"]);
  for (const e of eventList) {
    if (!validEvents.has(e)) {
      return new Response(`unknown event: ${e}`, { status: 400 });
    }
  }

  const signingSecret = randomBytes(32).toString("hex");

  const rows = await db
    .insert(webhook_subscriptions)
    .values({
      user_id: userId,
      deployment_id: typeof deployment_id === "string" ? deployment_id : null,
      url,
      events: eventList,
      signing_secret: signingSecret,
    })
    .returning({
      id: webhook_subscriptions.id,
      url: webhook_subscriptions.url,
      events: webhook_subscriptions.events,
      signing_secret: webhook_subscriptions.signing_secret,
      created_at: webhook_subscriptions.created_at,
    });

  const row = rows[0];
  if (!row) return new Response("insert failed", { status: 500 });

  return Response.json({ webhook: row }, { status: 201 });
}
