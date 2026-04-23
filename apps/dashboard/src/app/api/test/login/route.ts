import { NextResponse } from "next/server";
import { encode } from "@auth/core/jwt";

// This endpoint is ONLY available when VERUM_TEST_MODE=1 is set.
// We use a separate env flag instead of NODE_ENV because `next dev` always
// forces NODE_ENV=development regardless of the shell environment.
// The middleware matcher already excludes /api/test/* from auth checks.
export async function POST() {
  if (process.env.VERUM_TEST_MODE !== "1") {
    return new Response("not found", { status: 404 });
  }

  // Auth.js v5 uses AUTH_SECRET; fall back to NEXTAUTH_SECRET for CI compat.
  const secret = process.env.AUTH_SECRET ?? process.env.NEXTAUTH_SECRET;
  if (!secret) {
    return new Response("AUTH_SECRET not set", { status: 500 });
  }

  // Encode a minimal JWT session that next-auth v5 can verify.
  // token.sub is the internal user UUID stored by auth.ts jwt callback.
  const token = await encode({
    token: {
      sub: "00000000-0000-0000-0000-000000000099",
      name: "Verum Test User",
      email: "test@verum.dev",
      picture: null,
      github_login: "verum-test",
      github_access_token: "test-token",
      iat: Math.floor(Date.now() / 1000),
      exp: Math.floor(Date.now() / 1000) + 3600,
    },
    secret,
    // Auth.js v5 uses this salt for the session cookie
    salt: "authjs.session-token",
  });

  const res = NextResponse.json({ ok: true });
  res.cookies.set("authjs.session-token", token, {
    httpOnly: true,
    path: "/",
    sameSite: "lax",
    // No Secure flag — test runs over plain HTTP (localhost)
  });
  return res;
}
