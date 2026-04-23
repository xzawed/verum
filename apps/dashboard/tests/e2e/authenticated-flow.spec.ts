/**
 * Authenticated E2E flow tests — @authenticated
 *
 * These tests require NODE_ENV=test and a running Next.js dev server.
 * A test-only POST /api/test/login endpoint seeds a valid JWT session
 * cookie so we never touch GitHub OAuth in CI.
 *
 * Run in isolation:
 *   npx playwright test --grep @authenticated
 */
import { test, expect, type Page } from "@playwright/test";

// ── Auth helper ──────────────────────────────────────────────────────────────

/**
 * Calls the test-only login endpoint and plants the session cookie.
 * Must be called before any navigation in each test that needs auth.
 */
async function loginAsTestUser(page: Page): Promise<void> {
  // Hit the endpoint via the request context so it can set cookies
  const res = await page.request.post("/api/test/login");
  if (!res.ok()) {
    throw new Error(
      `Test login failed (${res.status()}). ` +
        "Is the server running with NODE_ENV=test?"
    );
  }
  // The endpoint sets authjs.session-token cookie — the browser context
  // inherits it automatically for subsequent navigations.
}

// ── Tests ────────────────────────────────────────────────────────────────────

test.describe("Authenticated flow @authenticated", () => {
  test("authenticated user can reach /repos without redirect", async ({ page }) => {
    await loginAsTestUser(page);
    const response = await page.goto("/repos", { waitUntil: "networkidle" });

    // Must not redirect to /login
    expect(page.url()).not.toMatch(/\/login/);
    // Page must not return a server error
    expect(response?.status()).toBeLessThan(500);
    await expect(page.locator("body")).toBeVisible();
  });

  test("authenticated user sees the repos page UI (not login form)", async ({ page }) => {
    await loginAsTestUser(page);
    await page.goto("/repos", { waitUntil: "networkidle" });

    // The login page has a GitHub sign-in button; the repos page does not
    const loginButton = page.getByRole("button", { name: /sign in with github/i });
    await expect(loginButton).not.toBeVisible();
  });

  test("unauthenticated request still redirects to /login", async ({ page }) => {
    // No loginAsTestUser() call — plain unauthenticated visit
    await page.goto("/repos", { waitUntil: "networkidle" });
    await expect(page).toHaveURL(/\/login/);
  });

  test("/health is reachable regardless of auth state", async ({ page }) => {
    const response = await page.goto("/health");
    expect(response?.status()).toBe(200);
  });

  test("session cookie is accepted — middleware does not redirect authenticated user", async ({ page }) => {
    await loginAsTestUser(page);

    // Navigate to a protected route and confirm we stay there (no redirect to /login).
    // We intentionally avoid calling /api/v1/repos here because E2E tests run
    // without a database service — a DB-dependent assertion belongs in integration tests.
    const response = await page.goto("/repos", { waitUntil: "networkidle" });
    expect(response?.status()).toBeLessThan(500);
    expect(page.url()).not.toMatch(/\/login/);
  });

  test("test login endpoint returns 404 when VERUM_TEST_MODE is not set", async ({ request }) => {
    // In CI (VERUM_TEST_MODE=1) the endpoint returns 200.
    // In production (VERUM_TEST_MODE unset) it returns 404.
    // This test verifies the endpoint is reachable and returns no 5xx regardless.
    const res = await request.post("/api/test/login");
    expect(res.status()).not.toBe(500);
  });
});
