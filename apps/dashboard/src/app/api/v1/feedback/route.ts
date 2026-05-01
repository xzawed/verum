import { z } from "zod";
import { updateFeedback } from "@/lib/db/jobs";
import { validateApiKey } from "@/lib/api/validateApiKey";
import { checkRateLimitDual, getClientIp } from "@/lib/rateLimit";

const FeedbackBodySchema = z.object({
  trace_id: z.string().uuid(),
  score: z.union([z.literal(-1), z.literal(1)]),
});

export async function POST(req: Request) {
  const apiKey = req.headers.get("x-verum-api-key") ?? "";
  if (!apiKey) return new Response("unauthorized", { status: 401 });

  // 30 feedback events/min per key; 60 per IP.
  const ip = getClientIp(req);
  const ipGate = await checkRateLimitDual(apiKey.slice(0, 16), 30, ip, 60);
  if (ipGate) return ipGate;

  const parsed = FeedbackBodySchema.safeParse(await req.json());
  if (!parsed.success) {
    return Response.json({ error: "invalid body" }, { status: 400 });
  }
  const body = parsed.data;

  const auth_result = await validateApiKey(apiKey);
  if (!auth_result) {
    return new Response("unauthorized", { status: 401 });
  }
  const { deploymentId } = auth_result;

  const ok = await updateFeedback(deploymentId, body.trace_id, body.score);
  if (!ok) return new Response("not found", { status: 404 });

  return new Response(null, { status: 204 });
}
