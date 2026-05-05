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

  test("unauthenticated request to /repos redirects to /login", async ({ page }) => {
    await page.goto("/repos", { waitUntil: "networkidle" });
    await expect(page).toHaveURL(/\/login/);
  });

  test("POST /api/v1/traces without X-Verum-API-Key returns 401", async ({ request }) => {
    const response = await request.post("/api/v1/traces", {
      headers: { "Content-Type": "application/json" },
      data: { deployment_id: "00000000-0000-4000-8000-000000000001", variant: "baseline", model: "gpt-4", input_tokens: 10, output_tokens: 5, latency_ms: 100 },
    });
    expect(response.status()).toBe(401);
  });

  test("POST /api/v1/traces with invalid API key returns 401", async ({ request }) => {
    const response = await request.post("/api/v1/traces", {
      headers: {
        "Content-Type": "application/json",
        "X-Verum-API-Key": "invalid-key-32-chars-long-xxxxxxxxx",
      },
      data: { deployment_id: "00000000-0000-4000-8000-000000000001", variant: "baseline", model: "gpt-4", input_tokens: 10, output_tokens: 5, latency_ms: 100 },
    });
    expect(response.status()).toBe(401);
  });
});
