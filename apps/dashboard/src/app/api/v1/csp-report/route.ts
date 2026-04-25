export async function POST(req: Request) {
  try {
    const body = await req.json();
    const report = (body["csp-report"] ?? body) as Record<string, unknown>;
    console.warn("[CSP VIOLATION]", JSON.stringify({
      blockedUri: report["blocked-uri"],
      violatedDirective: report["violated-directive"],
      documentUri: report["document-uri"],
      sourceFile: report["source-file"],
      lineNumber: report["line-number"],
    }));
  } catch {
    // Malformed report — ignore silently.
  }
  return new Response(null, { status: 204 });
}
