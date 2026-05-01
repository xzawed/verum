import { t } from "../index";

describe("t() translation function", () => {
  it("returns English string by default", () => {
    expect(t("common", "activate")).toBe("Activate");
  });

  it("returns Korean string for ko locale", () => {
    expect(t("common", "activate", "ko")).toBe("활성화");
  });

  it("returns Japanese string for ja locale", () => {
    expect(t("common", "activate", "ja")).toBe("有効化");
  });

  it("falls back to English when locale key is missing (hypothetical)", () => {
    // activate has all 3 locales, so test another key
    expect(t("common", "connected", "en")).toBe("Connected");
    expect(t("common", "connected", "ko")).toBe("연결됨");
    expect(t("common", "connected", "ja")).toBe("接続済み");
  });

  it("handles deploy group", () => {
    expect(t("deploy", "rollbackButton", "en")).toBe("Rollback");
    expect(t("deploy", "rollbackButton", "ko")).toBe("롤백");
    expect(t("deploy", "rollbackButton", "ja")).toBe("ロールバック");
  });

  it("handles observe group", () => {
    expect(t("observe", "panelTitle", "en")).toBe("Trace Detail");
    expect(t("observe", "panelTitle", "ko")).toBe("Trace 상세");
    expect(t("observe", "panelTitle", "ja")).toBe("トレース詳細");
  });

  it("handles trace group (backwards compat alias)", () => {
    expect(t("trace", "panelTitle", "en")).toBe("Trace Detail");
    expect(t("trace", "panelTitle", "ja")).toBe("トレース詳細");
  });

  it("handles stages group", () => {
    expect(t("stages", "stageAnalyze", "ja")).toBe("分析");
    expect(t("stages", "stageEvolve", "ja")).toBe("進化");
  });

  it("handles activation group", () => {
    expect(t("activation", "title", "en")).toBe("Activate Verum");
    expect(t("activation", "title", "ja")).toBe("Verum を有効化");
  });

  it("handles login group", () => {
    expect(t("login", "githubBtn", "ja")).toBe("GitHubでサインイン");
  });
});
