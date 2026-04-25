import { POST } from "../route";

describe("POST /api/v1/csp-report", () => {
  it("returns 204 for a valid CSP violation report", async () => {
    const body = {
      "csp-report": {
        "blocked-uri": "https://evil.com",
        "violated-directive": "default-src",
      },
    };
    const req = new Request("http://localhost", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const res = await POST(req);
    expect(res.status).toBe(204);
  });

  it("returns 204 even for malformed (non-JSON) body", async () => {
    const req = new Request("http://localhost", {
      method: "POST",
      headers: { "Content-Type": "text/plain" },
      body: "not-json",
    });
    const res = await POST(req);
    expect(res.status).toBe(204);
  });
});
