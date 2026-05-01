"use client";

import { useLocale } from "@/context/LocaleContext";
import { t } from "@/lib/i18n";

export function ReposHeader({ repoCount }: { repoCount: number }) {
  const { locale } = useLocale();

  return (
    <div>
      <h1 className="text-xl font-bold text-slate-900">
        {t("repos", "pageTitle", locale)}
        {repoCount > 0 && (
          <span className="ml-2 text-base font-normal text-slate-400">({repoCount})</span>
        )}
      </h1>
      <p className="mt-0.5 text-sm text-slate-500">
        {t("repos", "connectFirst", locale)}
      </p>
    </div>
  );
}
