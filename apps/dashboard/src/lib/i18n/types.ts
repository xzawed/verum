export type Locale = "en" | "ko" | "ja";
export const LOCALES = ["en", "ko", "ja"] as const satisfies readonly Locale[];
export const DEFAULT_LOCALE: Locale = "en";
export const LOCALE_LABELS: Record<Locale, string> = {
  en: "EN",
  ko: "한",
  ja: "日",
};
type LocaleMap = Record<Locale, string>;
export type StringGroup = Record<string, LocaleMap>;
