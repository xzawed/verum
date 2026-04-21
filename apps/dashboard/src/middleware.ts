import NextAuth from "next-auth";
import authConfig from "@/auth.config";

const { auth } = NextAuth(authConfig);
export { auth as middleware };

export const config = {
  matcher: ["/((?!api/auth|api/repos|login|health|_next|favicon).*)"],
};
