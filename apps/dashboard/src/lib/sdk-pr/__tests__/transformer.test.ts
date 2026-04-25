import { buildPrFileChanges } from "../transformer";
import type { LLMCallSite } from "../transformer";

const oneCallSite: LLMCallSite[] = [
  { file_path: "src/services/ai.ts", line: 5, sdk: "openai", function: "chat.completions.create", prompt_ref: null },
];

const sampleTsContent = [
  "import OpenAI from 'openai';",
  "const client = new OpenAI();",
  "",
  "async function call() {",
  "  const res = await client.chat.completions.create({",
  "    model: 'gpt-4',",
  "    messages: [],",
  "  });",
  "}",
].join("\n");

const samplePyContent = "import openai\nclient = openai.OpenAI()\nclient.chat.completions.create()\n";

describe("buildPrFileChanges", () => {
  // ── .env.example handling (both modes) ────────────────────────────────────

  it("creates .env.example when it does not exist", () => {
    const changes = buildPrFileChanges({ callSites: [], existingFiles: {}, repoFullName: "owner/repo", mode: "observe" });
    const envFile = changes.find((c) => c.path === ".env.example");
    expect(envFile).toBeDefined();
    expect(envFile!.content).toContain("VERUM_API_URL");
    expect(envFile!.content).toContain("VERUM_DEPLOYMENT_ID");
  });

  it("appends Verum vars to existing .env.example", () => {
    const changes = buildPrFileChanges({
      callSites: [],
      existingFiles: { ".env.example": "DATABASE_URL=postgres://localhost/mydb\n" },
      repoFullName: "owner/repo",
      mode: "observe",
    });
    const envFile = changes.find((c) => c.path === ".env.example");
    expect(envFile).toBeDefined();
    expect(envFile!.content).toContain("DATABASE_URL=postgres://localhost/mydb");
    expect(envFile!.content).toContain("VERUM_API_URL");
  });

  it("does NOT modify .env.example if VERUM_API_URL already present", () => {
    const changes = buildPrFileChanges({
      callSites: [],
      existingFiles: { ".env.example": "VERUM_API_URL=https://verum.dev\n" },
      repoFullName: "owner/repo",
      mode: "observe",
    });
    const envFile = changes.find((c) => c.path === ".env.example");
    expect(envFile).toBeUndefined();
  });

  // ── observe mode ──────────────────────────────────────────────────────────

  it("observe mode: returns only .env.example changes, never source files", () => {
    const changes = buildPrFileChanges({
      callSites: oneCallSite,
      existingFiles: { "src/services/ai.ts": sampleTsContent },
      repoFullName: "owner/repo",
      mode: "observe",
    });
    const sourceFile = changes.find((c) => c.path === "src/services/ai.ts");
    expect(sourceFile).toBeUndefined();
    // Only .env.example (or nothing if it already has VERUM_API_URL)
    expect(changes.every((c) => c.path === ".env.example")).toBe(true);
  });

  // ── bidirectional mode ────────────────────────────────────────────────────

  it("bidirectional mode: inserts Verum import for TypeScript files", () => {
    const changes = buildPrFileChanges({
      callSites: oneCallSite,
      existingFiles: { "src/services/ai.ts": sampleTsContent },
      repoFullName: "owner/repo",
      mode: "bidirectional",
    });
    const aiFile = changes.find((c) => c.path === "src/services/ai.ts");
    expect(aiFile).toBeDefined();
    expect(aiFile!.content).toContain('@verum/sdk/openai');
    // Import must appear right after the openai import line
    const lines = aiFile!.content.split("\n");
    const openaiIdx = lines.findIndex((l) => l.includes("from 'openai'") || l.includes("from \"openai\"") || l.includes("OpenAI from 'openai'"));
    const verumIdx = lines.findIndex((l) => l.includes("@verum/sdk/openai"));
    expect(verumIdx).toBe(openaiIdx + 1);
  });

  it("bidirectional mode: inserts Verum import for Python files", () => {
    const changes = buildPrFileChanges({
      callSites: [{ file_path: "src/service.py", line: 3, sdk: "openai", function: "create", prompt_ref: null }],
      existingFiles: { "src/service.py": samplePyContent },
      repoFullName: "owner/repo",
      mode: "bidirectional",
    });
    const pyFile = changes.find((c) => c.path === "src/service.py");
    expect(pyFile).toBeDefined();
    expect(pyFile!.content).toContain("import verum.openai");
  });

  it("bidirectional mode: does not duplicate import when called twice on TS file", () => {
    const firstPass = buildPrFileChanges({
      callSites: oneCallSite,
      existingFiles: { "src/services/ai.ts": sampleTsContent },
      repoFullName: "owner/repo",
      mode: "bidirectional",
    });
    const modified = firstPass.find((c) => c.path === "src/services/ai.ts")!.content;
    // Second call with already-modified content — file should NOT appear in changes.
    const secondPass = buildPrFileChanges({
      callSites: oneCallSite,
      existingFiles: { "src/services/ai.ts": modified },
      repoFullName: "owner/repo",
      mode: "bidirectional",
    });
    const secondChange = secondPass.find((c) => c.path === "src/services/ai.ts");
    expect(secondChange).toBeUndefined();
  });

  it("bidirectional mode: skips files with unsupported extensions", () => {
    const changes = buildPrFileChanges({
      callSites: [{ file_path: "src/config.json", line: 1, sdk: "openai", function: "create", prompt_ref: null }],
      existingFiles: { "src/config.json": "{}" },
      repoFullName: "owner/repo",
      mode: "bidirectional",
    });
    const jsonFile = changes.find((c) => c.path === "src/config.json");
    expect(jsonFile).toBeUndefined();
  });
});
