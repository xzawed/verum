import type { Metadata } from "next";
import { auth } from "@/auth";
import { AppShell } from "@/components/AppShell";
import "./globals.css";

export const metadata: Metadata = {
  title: "Verum",
  description: "Connect your repo. Auto-evolve your AI.",
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await auth();
  const username =
    ((session?.user as Record<string, unknown>)?.name as string)?.[0]?.toUpperCase() ?? "?";

  return (
    <html lang="en">
      <body className="bg-slate-50 text-slate-900 antialiased">
        <AppShell username={username}>{children}</AppShell>
      </body>
    </html>
  );
}
