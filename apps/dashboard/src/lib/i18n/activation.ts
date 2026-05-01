import type { StringGroup } from "./types";

export const activation = {
  title:             { en: "Activate Verum",    ko: "Verum 활성화",     ja: "Verum を有効化" },
  analysisInProgress:{ en: "Analysis in progress…", ko: "분석 중…",    ja: "分析中…" },
  readyDesc:         { en: "Your prompts and RAG index are ready. Click Activate to get your deployment credentials — then set 3 env vars and you're live.", ko: "프롬프트와 RAG 인덱스가 준비됐습니다. 활성화를 클릭하면 배포 자격 증명을 받을 수 있습니다.", ja: "プロンプトとRAGインデックスの準備が整いました。有効化をクリックしてデプロイ認証情報を取得してください。" },
  apiKeyCopyNow:     { en: "Copy your API key now — it won't be shown again.", ko: "API 키를 지금 복사하세요 — 다시 표시되지 않습니다.", ja: "APIキーを今すぐコピーしてください。再表示されません。" },
  waitingForTrace:   { en: "Waiting for first trace…", ko: "첫 번째 트레이스 대기 중…", ja: "初回トレース待機中…" },
  makeAnLlmCall:     { en: "Make an LLM call with your env vars set to see activity appear here.", ko: "환경 변수를 설정하고 LLM을 호출하면 여기에 활동이 표시됩니다.", ja: "環境変数を設定してLLMを呼び出すと、アクティビティがここに表示されます。" },
  tracesReceived:    { en: "Verum is receiving traces.", ko: "Verum이 트레이스를 수신하고 있습니다.", ja: "Verum はトレースを受信中です。" },
  noGeneration:      { en: "Waiting for GENERATE to complete before activation is available.", ko: "활성화 전에 GENERATE 완료를 기다리는 중입니다.", ja: "有効化前に GENERATE の完了を待っています。" },
  doneSaved:         { en: "Done — I've saved these", ko: "완료 — 저장했습니다", ja: "完了 — 保存しました" },
  deployment:        { en: "deployment", ko: "배포", ja: "デプロイ" },
  install:           { en: "1. Install",        ko: "1. 설치",           ja: "1. インストール" },
  setEnvVars:        { en: "2. Set env vars",   ko: "2. 환경 변수 설정", ja: "2. 環境変数を設定" },
  sdkNoteAutoInst:   { en: "verum-auto.pth instruments your OpenAI/Anthropic clients automatically at startup.", ko: "verum-auto.pth가 시작 시 OpenAI/Anthropic 클라이언트를 자동으로 계측합니다.", ja: "verum-auto.pth は起動時に OpenAI/Anthropic クライアントを自動的にインストゥルメントします。" },
  sdkNoteNodeOpts:   { en: "NODE_OPTIONS loads the SDK before your app code runs — no import needed.", ko: "NODE_OPTIONS는 앱 코드 실행 전에 SDK를 로드합니다 — import 불필요.", ja: "NODE_OPTIONS によりアプリコードの実行前に SDK が読み込まれます。importは不要です。" },
  errorPrefix:       { en: "Error: ",    ko: "오류: ",   ja: "エラー: " },
} as const satisfies StringGroup;
