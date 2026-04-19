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
        token.sub = String((profile as { id?: number }).id ?? token.sub);
        (token as Record<string, unknown>).github_login =
          (profile as { login?: string }).login ?? null;
      }
      return token;
    },
    async session({ session, token }) {
      if (session.user) {
        (session.user as Record<string, unknown>).id = token.sub;
        (session.user as Record<string, unknown>).github_login =
          (token as Record<string, unknown>).github_login ?? null;
      }
      return session;
    },
  },
});
