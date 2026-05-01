import type { StringGroup } from "./types";

export const common = {
  activate:       { en: "Activate",        ko: "활성화",       ja: "有効化" },
  activating:     { en: "Activating…",     ko: "활성화 중…",   ja: "有効化中…" },
  connected:      { en: "Connected",        ko: "연결됨",       ja: "接続済み" },
  loading:        { en: "Loading…",         ko: "불러오는 중…", ja: "読み込み中…" },
  refresh:        { en: "Refresh",          ko: "새로고침",     ja: "更新" },
  copyAll:        { en: "Copy all",         ko: "전체 복사",    ja: "すべてコピー" },
  copied:         { en: "Copied!",          ko: "복사됨!",      ja: "コピー済み！" },
  workerOnline:   { en: "Worker online",    ko: "워커 실행 중", ja: "ワーカー稼働中" },
  workerOffline:  { en: "Worker offline",   ko: "워커 오프라인", ja: "ワーカーオフライン" },
  running:        { en: "Running",          ko: "실행 중",      ja: "実行中" },
  done:           { en: "Done",             ko: "완료",         ja: "完了" },
  pending:        { en: "Pending",          ko: "대기",         ja: "保留中" },
  error:          { en: "Error",            ko: "오류",         ja: "エラー" },
  confidence:     { en: "Confidence",       ko: "신뢰도",       ja: "信頼度" },
  domain:         { en: "Domain",           ko: "도메인",       ja: "ドメイン" },
  chunks:         { en: "chunks",           ko: "청크",         ja: "チャンク" },
  variants:       { en: "variants",         ko: "변형",         ja: "バリアント" },
  callSite:       { en: "call site",        ko: "호출 지점",    ja: "呼び出し箇所" },
  callSites:      { en: "call sites",       ko: "호출 지점",    ja: "呼び出し箇所" },
} as const satisfies StringGroup;
