import NextAuth from "next-auth";
import authConfig from "@/auth.config";

const { auth } = NextAuth({
  ...authConfig,
  callbacks: {
    authorized({ auth: session, request }) {
      if (session) return true;
      // API routes return 401 JSON instead of redirecting to login
      if (request.nextUrl.pathname.startsWith("/api/")) {
        return new Response(JSON.stringify({ error: "Unauthorized" }), {
          status: 401,
          headers: { "Content-Type": "application/json" },
        });
      }
      return false; // UI routes redirect to signIn page
    },
  },
});

export default auth;

export const config = {
  // Exclude: auth endpoints, public SDK config, test routes, static assets, health
  matcher: [
    "/((?!api/auth|api/v1/deploy/.+/config|api/test|login|health|docs|_next|favicon).*)",
  ],
};
