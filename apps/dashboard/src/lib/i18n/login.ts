import type { StringGroup } from "./types";

export const login = {
  title:       { en: "Welcome back",          ko: "다시 오셨습니다",        ja: "おかえりなさい" },
  subtitle:    { en: "Sign in to your Verum account", ko: "Verum 계정에 로그인하세요", ja: "Verumアカウントにサインイン" },
  githubBtn:   { en: "Sign in with GitHub",   ko: "GitHub로 로그인",         ja: "GitHubでサインイン" },
  disclaimer:  { en: "By signing in, you agree to our Terms of Service.", ko: "로그인하면 서비스 약관에 동의하는 것으로 간주됩니다.", ja: "サインインすることで、利用規約に同意したものとみなされます。" },
} as const satisfies StringGroup;
