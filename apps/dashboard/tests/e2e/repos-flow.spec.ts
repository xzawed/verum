/**
 * Repos-flow E2E spec
 *
 * Conservative tests — no repo registration, no background jobs.
 * Requires: NODE_ENV=test + running dev server (playwright.config.ts webServer).
 *
 * Run in isolation:
 *   npx playwright test repos-flow
 */
import { test, expect, type Page } from "@playwright/test";

// ── Auth helper ───────────────────────────────────────────────────────────────

/**
 * Calls the test-only login endpoint and plants the session cookie.
 * Must be called before any navigation in each test that needs auth.
 */
async function loginAsTestUser(page: Page): Promise<void> {
  const res = await page.request.post("/api/test/login");
  if (!res.ok()) {
    throw new Error(
      `Test login failed (${res.status()}). ` +
        "Is the server running with NODE_ENV=test?",
    );
  }
  // The endpoint sets authjs.session-token cookie — the browser context
  // inherits it automatically for subsequent navigations.
}

// ── Tests ─────────────────────────────────────────────────────────────────────

test.describe("Repos flow", () => {
  test("redirects unauthenticated user to /login", async ({ page }) => {
    // No loginAsTestUser() — plain unauthenticated visit
    await page.goto("/repos", { waitUntil: "networkidle" });
    await expect(page).toHaveURL(/\/login/);
  });

  test("authenticated user can access /repos page", async ({ page }) => {
    await loginAsTestUser(page);
    await page.goto("/repos", { waitUntil: "networkidle" });

    // Must stay on /repos — not redirected to /login
    expect(page.url()).not.toMatch(/\/login/);

    // The repos page renders a recognisable heading
    const heading = page.getByRole("heading", { name: /repo/i });
    await expect(heading).toBeVisible();
  });

  test("sign-out button is visible when logged in", async ({ page }) => {
    await loginAsTestUser(page);
    await page.goto("/repos", { waitUntil: "networkidle" });

    // Auth.js renders a "Sign out" button in the session UI
    const signOutButton = page.getByRole("button", { name: /sign out/i });
    await expect(signOutButton).toBeVisible();
  });

  test("health endpoint returns 200", async ({ page }) => {
    const res = await page.request.get("/health");
    expect(res.ok()).toBe(true);
    expect(res.status()).toBe(200);
  });
});
