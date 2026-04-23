import { test, expect } from "@playwright/test";

test.describe("Smoke — no-auth endpoints", () => {
  test("GET /health returns 200 with ok status", async ({ request }) => {
    const response = await request.get("/health");
    expect(response.status()).toBe(200);
    const body = (await response.json()) as { status: string };
    expect(body.status).toBe("ok");
  });

  test("/docs page renders without authentication", async ({ page }) => {
    const response = await page.goto("/docs");
    expect(response?.status()).toBeLessThan(500);
    await expect(page.locator("body")).toBeVisible();
  });
});

test.describe("Smoke — authentication guard", () => {
  test("unauthenticated request to / redirects to /login", async ({ page }) => {
    await page.goto("/", { waitUntil: "networkidle" });
    await expect(page).toHaveURL(/\/login/);
  });

  test("unauthenticated request to /dashboard redirects to /login", async ({ page }) => {
    await page.goto("/dashboard", { waitUntil: "networkidle" });
    await expect(page).toHaveURL(/\/login/);
  });

  test("SDK API routes return 401 without API key", async ({ request }) => {
    const response = await request.post("/api/v1/traces", {
      headers: { "Content-Type": "application/json" },
      data: { deployment_id: "test", span_id: "s1", variant: "baseline", model: "gpt-4", input_tokens: 10, output_tokens: 5, latency_ms: 100 },
    });
    expect(response.status()).toBe(401);
  });
});
