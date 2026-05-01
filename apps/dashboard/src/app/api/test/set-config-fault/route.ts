import { setConfigFault, resetConfigFault } from "@/lib/test/configFault";

export async function POST(req: Request): Promise<Response> {
  if (process.env.VERUM_TEST_MODE !== "1") {
    return new Response("not found", { status: 404 });
  }
  const body = (await req.json()) as { count?: number };
  const count = typeof body.count === "number" ? body.count : 1;
  setConfigFault(count);
  return Response.json({ ok: true, count });
}

export async function DELETE(): Promise<Response> {
  if (process.env.VERUM_TEST_MODE !== "1") {
    return new Response("not found", { status: 404 });
  }
  resetConfigFault();
  return Response.json({ ok: true });
}
