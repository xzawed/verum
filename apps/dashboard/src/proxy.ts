import NextAuth from "next-auth";
import authConfig from "@/auth.config";

const { auth } = NextAuth({
  ...authConfig,
  pages: { signIn: "/login" },
});

export default auth;

export const config = {
  // Exclude all API routes (they handle their own auth), plus static assets and public pages.
  // Route handlers that require auth perform their own session check.
  matcher: [
    "/((?!api|_next/static|_next/image|favicon.ico|health|docs|login).*)",
  ],
};
