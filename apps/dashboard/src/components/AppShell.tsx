"use client";

import { usePathname } from "next/navigation";
import { Sidebar } from "./Sidebar";

interface Props {
  children: React.ReactNode;
  username: string;
}

// Routes that render full-page without the sidebar shell
const NO_SHELL_PREFIXES = ["/login", "/health"];

export function AppShell({ children, username }: Props) {
  const pathname = usePathname();

  const noShell = NO_SHELL_PREFIXES.some((prefix) => pathname.startsWith(prefix));

  if (noShell) {
    return <>{children}</>;
  }

  return (
    <div className="flex h-screen flex-col overflow-hidden sm:flex-row">
      <Sidebar pathname={pathname} username={username} />
      <main className="flex-1 min-h-0 min-w-0 overflow-auto">{children}</main>
    </div>
  );
}
