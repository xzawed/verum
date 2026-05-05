import type { Page } from "@playwright/test";

/**
 * Calls the test-only /api/test/login endpoint and plants a session cookie.
 * Must be called before any authenticated navigation in E2E tests.
 * Requires NODE_ENV=test and a running Next.js dev server.
 */
export async function loginAsTestUser(page: Page): Promise<void> {
  const res = await page.request.post("/api/test/login");
  if (!res.ok()) {
    throw new Error(
      `Test login failed (${res.status()}). ` +
        "Is the server running with NODE_ENV=test?"
    );
  }
}
