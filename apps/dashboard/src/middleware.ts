import NextAuth from "next-auth";
import authConfig from "@/auth.config";

export const { auth: middleware } = NextAuth({
  ...authConfig,
  callbacks: {
    authorized({ auth, request }) {
      if (auth) return true;
      // API routes return 401 JSON instead of redirecting to login
      if (request.nextUrl.pathname.startsWith("/api/")) {
        return Response.json({ error: "Unauthorized" }, { status: 401 });
      }
      return false; // UI routes redirect to signIn page
    },
  },
});

export const config = {
  // Exclude: auth endpoints, public SDK config, test routes, static assets, health
  matcher: [
    "/((?!api/auth|api/v1/deploy/.+/config|api/test|login|health|docs|_next|favicon).*)",
  ],
};
