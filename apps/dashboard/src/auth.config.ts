import GitHub from "next-auth/providers/github";
import type { NextAuthConfig } from "next-auth";
import { GITHUB_API_BASE, GITHUB_OAUTH_BASE } from "@/lib/github/constants";

const isOverridden = GITHUB_OAUTH_BASE !== "https://github.com";

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
