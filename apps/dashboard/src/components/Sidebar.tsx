import Link from "next/link";

interface Props {
  pathname: string;
  username: string;
}

function NavItem({
  href,
  active,
  title,
  children,
}: {
  href: string;
  active: boolean;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      title={title}
      className={`flex h-9 w-9 items-center justify-center rounded-lg transition-colors ${
        active
          ? "bg-indigo-100 text-indigo-600"
          : "text-slate-400 hover:bg-slate-100 hover:text-slate-600"
      }`}
    >
      {children}
    </Link>
  );
}

export function Sidebar({ pathname, username }: Props) {
  const reposActive =
    pathname.startsWith("/repos") ||
    pathname.startsWith("/analyses") ||
    pathname.startsWith("/infer") ||
    pathname.startsWith("/harvest") ||
    pathname.startsWith("/generate") ||
    pathname.startsWith("/deploy") ||
    pathname.startsWith("/retrieve");
  const docsActive = pathname.startsWith("/docs");

  return (
    <aside className="flex h-12 w-full flex-shrink-0 flex-row items-center gap-2 border-b border-slate-200 bg-white px-3 sm:h-screen sm:w-14 sm:flex-col sm:gap-0 sm:border-b-0 sm:border-r sm:px-0 sm:py-3">
      {/* Logo badge */}
      <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-indigo-500 sm:mb-4">
        <span className="text-sm font-black text-white">V</span>
      </div>

      {/* Nav items */}
      <nav className="flex flex-row gap-1 sm:flex-col">
        <NavItem href="/repos" active={reposActive} title="Repositories">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" />
            <rect x="3" y="14" width="7" height="7" /><rect x="14" y="14" width="7" height="7" />
          </svg>
        </NavItem>

        <NavItem href="/docs" active={docsActive} title="Documentation">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
            <polyline points="14 2 14 8 20 8" />
          </svg>
        </NavItem>
      </nav>

      {/* Spacer */}
      <div className="flex-1" />

      {/* User avatar */}
      <div
        className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-slate-200 text-xs font-semibold text-slate-600"
        title="Account"
      >
        {username}
      </div>
    </aside>
  );
}
