import { LanguageSwitcher } from "./LanguageSwitcher";

export function Header() {
  return (
    <header className="flex h-12 flex-shrink-0 items-center justify-end border-b border-slate-100 bg-white px-4">
      <LanguageSwitcher />
    </header>
  );
}
