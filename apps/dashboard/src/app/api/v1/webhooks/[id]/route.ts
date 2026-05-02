import { auth } from "@/auth";
import { db } from "@/lib/db/client";
import { webhook_subscriptions } from "@/lib/db/schema";
import { and, eq } from "drizzle-orm";

export async function DELETE(
  _req: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const session = await auth();
  if (!session?.user) return new Response("unauthorized", { status: 401 });
  const userId = session.user.id as string;
  const { id } = await params;

  const deleted = await db
    .delete(webhook_subscriptions)
    .where(
      and(
        eq(webhook_subscriptions.id, id),
        eq(webhook_subscriptions.user_id, userId),
      ),
    )
    .returning({ id: webhook_subscriptions.id });

  if (!deleted[0]) return new Response("not found", { status: 404 });
  return new Response(null, { status: 204 });
}
