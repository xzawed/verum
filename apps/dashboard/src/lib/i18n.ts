/**
 * UI string map — single source of truth for all user-visible text.
 * Add translations by extending the locale map below.
 */

type Locale = "en" | "ko";

const strings = {
  deploy: {
    rolledBackLabel: { en: "Rolled back", ko: "롤백됨" },
    rolledBackDesc: { en: "Reverted to baseline prompt.", ko: "기본 프롬프트로 복원되었습니다." },
    trafficSplitHeading: { en: "Traffic Split", ko: "트래픽 조정" },
    trafficRefreshHint: {
      en: "Refresh the page after changing traffic to see updates.",
      ko: "트래픽 변경 후 페이지를 새로고침하면 반영됩니다.",
    },
    rollbackButton: { en: "Rollback", ko: "롤백" },
  },
  generate: {
    startButton: { en: "Start Generation", ko: "생성 시작" },
    generating: { en: "Generating…", ko: "생성 중…" },
    refresh: { en: "Refresh", ko: "새로고침" },
    metricProfileHeading: { en: "Metric Profile", ko: "메트릭 프로파일" },
    promptVariantsHeading: { en: "Prompt Variants", ko: "프롬프트 Variants" },
    evalPairsHeading: { en: "Eval Pairs (first 5)", ko: "Eval Pairs (처음 5개)" },
    approveButton: { en: "Approve → DEPLOY", ko: "승인 → DEPLOY" },
  },
} as const;

const DEFAULT_LOCALE: Locale = "en";

type StringGroup = typeof strings;

export function t<
  G extends keyof StringGroup,
  K extends keyof StringGroup[G],
>(group: G, key: K, locale: Locale = DEFAULT_LOCALE): string {
  const entry = strings[group][key] as Record<Locale, string>;
  return entry[locale] ?? entry[DEFAULT_LOCALE];
}
