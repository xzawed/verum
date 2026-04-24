import GitHub from "next-auth/providers/github";
import type { NextAuthConfig } from "next-auth";
import { GITHUB_API_BASE, GITHUB_OAUTH_BASE } from "@/lib/github/constants";

const isOverridden = GITHUB_OAUTH_BASE !== "https://github.com";

// Security: reject arbitrary GITHUB_OAUTH_BASE to prevent SSRF/OAuth-phishing.
// Overrides are only accepted when VERUM_TEST_MODE=1 AND the target is a known
// local/mock host. Any other override (including in "production" without test mode)
// causes a hard failure at server startup.
if (isOverridden) {
  const isTestMode = process.env.VERUM_TEST_MODE === "1";
  const isAllowedDevHost =
    GITHUB_OAUTH_BASE.startsWith("http://mock-providers:") ||
    /^http:\/\/localhost(:\d+)?$/.test(GITHUB_OAUTH_BASE);

  if (!isTestMode || !isAllowedDevHost) {
    throw new Error(
      `GITHUB_OAUTH_BASE "${GITHUB_OAUTH_BASE}" override rejected. ` +
        `Only http://mock-providers:* and http://localhost:* are accepted when VERUM_TEST_MODE=1.`,
    );
  }
}

export default {
  providers: [
    GitHub(
      isOverridden
        ? {
            authorization: {
              url: `${GITHUB_OAUTH_BASE}/login/oauth/authorize`,
              params: { scope: "read:user user:email public_repo" },
            },
            token: `${GITHUB_OAUTH_BASE}/login/oauth/access_token`,
            userinfo: `${GITHUB_API_BASE}/user`,
          }
        : {
            authorization: { params: { scope: "read:user user:email public_repo" } },
          },
    ),
  ],
  session: { strategy: "jwt" },
} satisfies NextAuthConfig;
