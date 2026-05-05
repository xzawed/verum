/**
 * Repos-flow E2E spec
 *
 * Conservative tests — no repo registration, no background jobs.
 * Requires: NODE_ENV=test + running dev server (playwright.config.ts webServer).
 *
 * Run in isolation:
 *   npx playwright test repos-flow
 */
import { test, expect } from "@playwright/test";
import { loginAsTestUser } from "./helpers";

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
    const heading = page.getByRole("heading", { level: 1, name: /repo/i });
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
