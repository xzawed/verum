import type { Metadata, Viewport } from "next";
import { auth } from "@/auth";
import { AppShell } from "@/components/AppShell";
import { LocaleProvider } from "@/context/LocaleContext";
import "./globals.css";

export const metadata: Metadata = {
  title: "Verum",
  description: "Connect your repo. Auto-evolve your AI.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
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
        <LocaleProvider>
          <AppShell username={username}>{children}</AppShell>
        </LocaleProvider>
      </body>
    </html>
  );
}
