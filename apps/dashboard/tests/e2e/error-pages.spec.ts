/**
 * Error-pages E2E spec
 *
 * Verifies 404 and error handling for unknown routes and protected resources.
 * Conservative — no DB required.
 *
 * Run in isolation:
 *   npx playwright test error-pages
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

// ── 404 tests ─────────────────────────────────────────────────────────────────

test.describe("404 — unknown public routes", () => {
  test("GET /nonexistent returns 404", async ({ request }) => {
    const res = await request.get("/nonexistent-route-xyz");
    expect(res.status()).toBe(404);
  });

  test("GET /api/nonexistent returns 404", async ({ request }) => {
    const res = await request.get("/api/nonexistent-endpoint");
    expect(res.status()).toBe(404);
  });
});

test.describe("404 — authenticated access to unknown resources", () => {
  const FAKE_UUID = "00000000-0000-4000-8000-000000000002";

  test("authenticated user gets 404 for unknown repo ID", async ({ page }) => {
    await loginAsTestUser(page);
    const response = await page.goto(`/repos/${FAKE_UUID}`, {
      waitUntil: "networkidle",
    });
    expect(response?.status()).toBe(404);
  });

  test("authenticated user gets 404 for unknown inference ID", async ({
    page,
  }) => {
    await loginAsTestUser(page);
    const response = await page.goto(`/infer/${FAKE_UUID}`, {
      waitUntil: "networkidle",
    });
    expect(response?.status()).toBe(404);
  });

  test("authenticated user gets 404 for unknown generate ID", async ({
    page,
  }) => {
    await loginAsTestUser(page);
    const response = await page.goto(`/generate/${FAKE_UUID}`, {
      waitUntil: "networkidle",
    });
    expect(response?.status()).toBe(404);
  });
});

test.describe("Protected routes — unauthenticated 404 vs redirect behaviour", () => {
  const FAKE_UUID = "00000000-0000-4000-8000-000000000003";

  // Next.js auth middleware redirects to /login before reaching the page handler,
  // so unauthenticated users see /login, not 404.
  test("unauthenticated user on /repos/[id] is redirected to /login", async ({
    page,
  }) => {
    await page.goto(`/repos/${FAKE_UUID}`, { waitUntil: "networkidle" });
    await expect(page).toHaveURL(/\/login/);
  });

  test("unauthenticated user on /deploy/[id] is redirected to /login", async ({
    page,
  }) => {
    await page.goto(`/deploy/${FAKE_UUID}`, { waitUntil: "networkidle" });
    await expect(page).toHaveURL(/\/login/);
  });
});

test.describe("No 500 errors on core pages", () => {
  test("/health never returns 5xx", async ({ request }) => {
    const res = await request.get("/health");
    expect(res.status()).toBeLessThan(500);
  });

  test("/login page renders without 5xx", async ({ page }) => {
    const response = await page.goto("/login");
    expect(response?.status()).toBeLessThan(500);
    await expect(page.locator("body")).toBeVisible();
  });
});
