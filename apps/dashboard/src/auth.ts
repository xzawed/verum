import NextAuth from "next-auth";
import GitHub from "next-auth/providers/github";

export const { handlers, signIn, signOut, auth } = NextAuth({
  providers: [
    GitHub({
      authorization: { params: { scope: "read:user user:email" } },
    }),
  ],
  session: { strategy: "jwt" },
  callbacks: {
    async jwt({ token, profile }) {
      if (profile) {
        // Persist GitHub numeric ID and login into the token so FastAPI can
        // use them for user lookup without an extra API call.
        token.sub = String((profile as { id?: number }).id ?? token.sub);
        (token as Record<string, unknown>).github_login =
          (profile as { login?: string }).login ?? null;
      }
      return token;
    },
  },
});
