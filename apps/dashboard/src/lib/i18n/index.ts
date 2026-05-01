export type { Locale, StringGroup } from "./types";
export { LOCALES, DEFAULT_LOCALE, LOCALE_LABELS } from "./types";
export { common } from "./common";
export { repos } from "./repos";
export { stages } from "./stages";
export { activation } from "./activation";
export { observe } from "./observe";
export { deploy } from "./deploy";
export { generate } from "./generate";
export { login } from "./login";

import { common } from "./common";
import { repos } from "./repos";
import { stages } from "./stages";
import { activation } from "./activation";
import { observe } from "./observe";
import { deploy } from "./deploy";
import { generate } from "./generate";
import { login } from "./login";
import type { Locale } from "./types";

// Backwards-compat alias: existing callers use t("trace", ...)
// trace keys are a subset of observe keys
const ALL_STRINGS = {
  common,
  repos,
  stages,
  activation,
  observe,
  deploy,
  generate,
  login,
  trace: observe,
} as const;

export type GroupName = keyof typeof ALL_STRINGS;
export type KeyOf<G extends GroupName> = keyof (typeof ALL_STRINGS)[G];

/** Type-safe translation function. Falls back to DEFAULT_LOCALE ("en") if locale string is absent. */
export function t<G extends GroupName, K extends KeyOf<G>>(
  group: G,
  key: K,
  locale: Locale = "en",
): string {
  const entry = ALL_STRINGS[group][key] as Record<Locale, string>;
  return entry[locale] ?? entry["en"];
}
