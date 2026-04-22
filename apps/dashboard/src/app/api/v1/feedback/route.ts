import { updateFeedback } from "@/lib/db/jobs";

export async function POST(req: Request) {
  const apiKey = req.headers.get("x-verum-api-key") ?? "";
  if (!apiKey) return new Response("unauthorized", { status: 401 });

  const body = await req.json() as { trace_id: string; score: number };

  if (!body.trace_id || (body.score !== 1 && body.score !== -1)) {
    return new Response("score must be 1 or -1", { status: 400 });
  }

  // API key is the deployment_id; use it to scope the feedback update
  const ok = await updateFeedback(apiKey, body.trace_id, body.score);
  if (!ok) return new Response("not found", { status: 404 });

  return new Response(null, { status: 204 });
}
