import NextAuth from "next-auth";
import { upsertUser } from "@/lib/db/queries";
import authConfig from "./auth.config";

export const { handlers, signIn, signOut, auth } = NextAuth({
  ...authConfig,
  callbacks: {
    async jwt({ token, profile }) {
      if (profile) {
        // profile is only present on initial sign-in — upsert user and store internal UUID
        const user = await upsertUser({
          githubId: (profile as { id?: number }).id!,
          githubLogin: (profile as { login?: string }).login ?? "",
          email: (profile as { email?: string }).email ?? null,
          avatarUrl: (profile as { avatar_url?: string }).avatar_url ?? null,
        });
        token.sub = user.id; // internal UUID, not GitHub numeric ID
        (token as Record<string, unknown>).github_login =
          (profile as { login?: string }).login ?? null;
      }
      return token;
    },
    async session({ session, token }) {
      if (session.user) {
        (session.user as unknown as Record<string, unknown>).id = token.sub;
        (session.user as unknown as Record<string, unknown>).github_login =
          (token as Record<string, unknown>).github_login ?? null;
      }
      return session;
    },
  },
});
