import type { StringGroup } from "./types";

export const generate = {
  startButton:          { en: "Start Generation",       ko: "생성 시작",           ja: "生成を開始" },
  generating:           { en: "Generating…",            ko: "생성 중…",            ja: "生成中…" },
  refresh:              { en: "Refresh",                ko: "새로고침",            ja: "更新" },
  metricProfileHeading: { en: "Metric Profile",         ko: "메트릭 프로파일",     ja: "メトリクスプロファイル" },
  promptVariantsHeading:{ en: "Prompt Variants",        ko: "프롬프트 Variants",   ja: "プロンプトバリアント" },
  evalPairsHeading:     { en: "Eval Pairs (first 5)",   ko: "Eval Pairs (처음 5개)", ja: "評価ペア（最初の5件）" },
  approveButton:        { en: "Approve → DEPLOY",       ko: "승인 → DEPLOY",       ja: "承認 → デプロイ" },
} as const satisfies StringGroup;
