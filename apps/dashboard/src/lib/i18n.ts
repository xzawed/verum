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
  trace: {
    panelTitle: { en: "Trace Detail", ko: "Trace 상세" },
    loading: { en: "Loading…", ko: "불러오는 중..." },
    notFound: { en: "Trace not found.", ko: "Trace를 찾을 수 없습니다." },
    sectionMeta: { en: "Metadata", ko: "기본 정보" },
    sectionLatency: { en: "Latency", ko: "지연 시간" },
    sectionCost: { en: "Cost", ko: "비용 분석" },
    sectionJudge: { en: "Judge Score", ko: "Judge 평가" },
    labelId: { en: "ID", ko: "ID" },
    labelVariant: { en: "Variant", ko: "Variant" },
    labelFeedback: { en: "Feedback", ko: "피드백" },
    labelTimestamp: { en: "Time", ko: "시각" },
    labelInputTokens: { en: "Input tokens", ko: "입력 토큰" },
    labelOutputTokens: { en: "Output tokens", ko: "출력 토큰" },
    labelTotalCost: { en: "Total cost", ko: "총 비용" },
    feedbackPositive: { en: "👍 Positive", ko: "👍 긍정" },
    feedbackNegative: { en: "👎 Negative", ko: "👎 부정" },
    feedbackNone: { en: "None", ko: "없음" },
    errorPrefix: { en: "Error: ", ko: "오류: " },
    judgePending: { en: "Scoring… (up to 60s)", ko: "채점 중... (최대 60초 소요)" },
    judgedAt: { en: "Scored: ", ko: "채점: " },
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
