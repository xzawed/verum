import type { StringGroup } from "./types";

export const deploy = {
  pageTitle:        { en: "DEPLOY — Canary Deployment", ko: "DEPLOY — 카나리 배포", ja: "DEPLOY — カナリアデプロイ" },
  rolledBackLabel:  { en: "Rolled back",     ko: "롤백됨",                  ja: "ロールバック済み" },
  rolledBackDesc:   { en: "Reverted to baseline prompt.", ko: "기본 프롬프트로 복원되었습니다.", ja: "ベースラインプロンプトに戻しました。" },
  trafficSplitHeading: { en: "Traffic Split", ko: "트래픽 조정",            ja: "トラフィック分配" },
  trafficRefreshHint:  { en: "Refresh the page after changing traffic to see updates.", ko: "트래픽 변경 후 페이지를 새로고침하면 반영됩니다.", ja: "トラフィックを変更後、ページを更新すると反映されます。" },
  rollbackButton:   { en: "Rollback",        ko: "롤백",                    ja: "ロールバック" },
} as const satisfies StringGroup;
