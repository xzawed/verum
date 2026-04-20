import GitHub from "next-auth/providers/github";
import type { NextAuthConfig } from "next-auth";

export default {
  providers: [
    GitHub({
      authorization: { params: { scope: "read:user user:email public_repo" } },
    }),
  ],
  session: { strategy: "jwt" },
} satisfies NextAuthConfig;
