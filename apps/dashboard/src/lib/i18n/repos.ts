import type { StringGroup } from "./types";

export const repos = {
  pageTitle:      { en: "Repositories",           ko: "저장소",                   ja: "リポジトリ" },
  addRepository:  { en: "Add Repository",          ko: "저장소 추가",              ja: "リポジトリを追加" },
  connectFirst:   { en: "Connect a repo to get started", ko: "시작하려면 저장소를 연결하세요", ja: "始めるにはリポジトリを接続してください" },
  noRepos:        { en: "No repositories yet",     ko: "등록된 저장소가 없습니다",   ja: "リポジトリがまだありません" },
  analyzeBtn:     { en: "Analyze",                 ko: "분석",                     ja: "分析する" },
  deleteBtn:      { en: "Delete",                  ko: "삭제",                     ja: "削除" },
  deleteConfirm:  { en: "Delete this repository?", ko: "이 저장소를 삭제하시겠습니까?", ja: "このリポジトリを削除しますか？" },
  deleting:       { en: "Deleting…",               ko: "삭제 중…",                 ja: "削除中…" },
  connecting:     { en: "Connecting…",             ko: "연결 중…",                 ja: "接続中…" },
  connect:        { en: "Connect",                 ko: "연결",                     ja: "接続" },
  alreadyAdded:   { en: "Already added",           ko: "이미 추가됨",              ja: "追加済み" },
  searchRepos:    { en: "Search repositories…",    ko: "저장소 검색…",             ja: "リポジトリを検索…" },
  selectRepo:     { en: "Select a repository",     ko: "저장소를 선택하세요",       ja: "リポジトリを選択してください" },
  branch:         { en: "branch",                  ko: "브랜치",                   ja: "ブランチ" },
  loadingRepos:   { en: "Loading repositories…",   ko: "저장소 불러오는 중…",      ja: "リポジトリを読み込み中…" },
  repos:          { en: "Repos",                   ko: "저장소",                   ja: "リポジトリ" },
  docs:           { en: "Docs",                    ko: "문서",                     ja: "ドキュメント" },
} as const satisfies StringGroup;
