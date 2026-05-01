"use client";

import { motion } from "framer-motion";
import { LOCALES, LOCALE_LABELS } from "@/lib/i18n/types";
import { useLocale } from "@/context/LocaleContext";

export function LanguageSwitcher() {
  const { locale, setLocale } = useLocale();

  return (
    <div className="flex items-center gap-0.5 rounded-lg bg-slate-100 p-0.5">
      {LOCALES.map((loc) => (
        <button
          key={loc}
          onClick={() => setLocale(loc)}
          className="relative px-2.5 py-1 text-xs font-semibold transition-colors"
          style={{ color: locale === loc ? "#4f46e5" : "#94a3b8" }}
        >
          {/* Framer Motion animated background pill */}
          {locale === loc && (
            <motion.span
              layoutId="locale-pill"
              className="absolute inset-0 rounded-md bg-white shadow-sm"
              transition={{ type: "spring", stiffness: 400, damping: 30 }}
            />
          )}
          <span className="relative z-10">{LOCALE_LABELS[loc]}</span>
        </button>
      ))}
    </div>
  );
}
