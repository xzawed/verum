/**
 * DEPLOY page E2E spec
 *
 * Conservative tests — no real deployment in DB.
 * Covers auth guard, 404 for unknown deployment IDs, and SDK API auth.
 *
 * Run in isolation:
 *   npx playwright test deploy-flow
 */
import { test, expect, type Page } from "@playwright/test";

// ── Auth helper ────────────────────────────────────────────────────────────────

async function loginAsTestUser(page: Page): Promise<void> {
  const res = await page.request.post("/api/test/login");
  if (!res.ok()) {
    throw new Error(
      `Test login failed (${res.status()}). ` +
        "Is the server running with NODE_ENV=test?",
    );
  }
}

const FAKE_UUID = "00000000-0000-4000-8000-000000000001";

// ── Tests ─────────────────────────────────────────────────────────────────────

test.describe("DEPLOY page — auth guard", () => {
  test("unauthenticated user is redirected to /login", async ({ page }) => {
    await page.goto(`/deploy/${FAKE_UUID}`, { waitUntil: "networkidle" });
    await expect(page).toHaveURL(/\/login/);
  });

  test("authenticated user gets 404 for unknown deployment ID", async ({ page }) => {
    await loginAsTestUser(page);
    const response = await page.goto(`/deploy/${FAKE_UUID}`, { waitUntil: "networkidle" });
    // Next.js notFound() returns 404
    expect(response?.status()).toBe(404);
  });

  test("authenticated user stays off /login for deploy routes", async ({ page }) => {
    await loginAsTestUser(page);
    await page.goto(`/deploy/${FAKE_UUID}`, { waitUntil: "networkidle" });
    expect(page.url()).not.toMatch(/\/login/);
  });
});

test.describe("SDK API — /api/v1/experiments auth", () => {
  test("missing API key returns 401 or 400", async ({ request }) => {
    const res = await request.get(
      `/api/v1/experiments?deployment_id=${FAKE_UUID}`,
    );
    // Without a valid API key, must reject — not 500
    expect(res.status()).toBeLessThan(500);
    expect(res.status()).not.toBe(200);
  });
});

test.describe("SDK API — /api/v1/feedback auth", () => {
  test("missing API key returns 401", async ({ request }) => {
    const res = await request.post("/api/v1/feedback", {
      headers: { "Content-Type": "application/json" },
      data: { trace_id: FAKE_UUID, score: 1 },
    });
    expect(res.status()).toBe(401);
  });
});

test.describe("SDK API — /api/v1/retrieve-sdk auth", () => {
  test("missing API key returns 401", async ({ request }) => {
    const res = await request.post("/api/v1/retrieve-sdk", {
      headers: { "Content-Type": "application/json" },
      data: { query: "test", collection_name: "arcana", top_k: 3 },
    });
    expect(res.status()).toBe(401);
  });
});
