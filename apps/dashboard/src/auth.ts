import NextAuth from "next-auth";
import { upsertUser } from "@/lib/db/queries";
import authConfig from "./auth.config";

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export const { handlers, signIn, signOut, auth } = NextAuth({
  ...authConfig,
  callbacks: {
    async jwt({ token, profile, account }) {
      if (account?.access_token) {
        token.github_access_token = account.access_token;
      }
      if (profile) {
        // Initial sign-in: upsert user and store internal UUID
        const user = await upsertUser({
          githubId: (profile as { id?: number }).id!,
          githubLogin: (profile as { login?: string }).login ?? "",
          email: (profile as { email?: string }).email ?? null,
          avatarUrl: (profile as { avatar_url?: string }).avatar_url ?? null,
        });
        token.sub = user.id;
        token.github_login = (profile as { login?: string }).login ?? null;
      } else if (token.sub && !UUID_RE.test(token.sub)) {
        // Legacy session: token.sub is GitHub numeric ID — migrate to internal UUID
        const githubId = parseInt(token.sub, 10);
        if (!isNaN(githubId)) {
          const user = await upsertUser({
            githubId,
            githubLogin: String(token.github_login ?? ""),
            email: null,
            avatarUrl: null,
          });
          token.sub = user.id;
        }
      }
      return token;
    },
    async session({ session, token }) {
      if (session.user) {
        session.user.id = token.sub ?? "";
        session.user.github_login = (token.github_login as string | null) ?? null;
        session.user.github_access_token = (token.github_access_token as string | null) ?? null;
      }
      return session;
    },
  },
});
