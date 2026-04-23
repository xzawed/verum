import { t } from "../i18n";

describe("t() — en (default locale)", () => {
  it("returns deploy strings", () => {
    expect(t("deploy", "rolledBackLabel")).toBe("Rolled back");
    expect(t("deploy", "rolledBackDesc")).toBe("Reverted to baseline prompt.");
    expect(t("deploy", "rollbackButton")).toBe("Rollback");
    expect(t("deploy", "trafficSplitHeading")).toBe("Traffic Split");
  });

  it("returns generate strings", () => {
    expect(t("generate", "startButton")).toBe("Start Generation");
    expect(t("generate", "generating")).toBe("Generating…");
    expect(t("generate", "refresh")).toBe("Refresh");
    expect(t("generate", "approveButton")).toBe("Approve → DEPLOY");
  });

  it("returns trace metadata strings", () => {
    expect(t("trace", "panelTitle")).toBe("Trace Detail");
    expect(t("trace", "loading")).toBe("Loading…");
    expect(t("trace", "notFound")).toBe("Trace not found.");
    expect(t("trace", "sectionMeta")).toBe("Metadata");
  });

  it("returns trace feedback strings", () => {
    expect(t("trace", "feedbackPositive")).toBe("👍 Positive");
    expect(t("trace", "feedbackNegative")).toBe("👎 Negative");
    expect(t("trace", "feedbackNone")).toBe("None");
  });

  it("returns trace cost and label strings", () => {
    expect(t("trace", "labelId")).toBe("ID");
    expect(t("trace", "labelTotalCost")).toBe("Total cost");
    expect(t("trace", "judgePending")).toBe("Scoring… (up to 60s)");
  });
});

describe("t() — ko locale", () => {
  it("returns Korean deploy strings", () => {
    expect(t("deploy", "rolledBackLabel", "ko")).toBe("롤백됨");
    expect(t("deploy", "rollbackButton", "ko")).toBe("롤백");
  });

  it("returns Korean generate strings", () => {
    expect(t("generate", "startButton", "ko")).toBe("생성 시작");
    expect(t("generate", "refresh", "ko")).toBe("새로고침");
  });

  it("returns Korean trace strings", () => {
    expect(t("trace", "loading", "ko")).toBe("불러오는 중...");
    expect(t("trace", "notFound", "ko")).toBe("Trace를 찾을 수 없습니다.");
    expect(t("trace", "sectionCost", "ko")).toBe("비용 분석");
    expect(t("trace", "feedbackPositive", "ko")).toBe("👍 긍정");
  });
});
