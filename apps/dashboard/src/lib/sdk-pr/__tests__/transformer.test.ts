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

  // ── dependency file patching ──────────────────────────────────────────────

  it("bidirectional mode: adds @verum/sdk to package.json dependencies", () => {
    const pkgJson = JSON.stringify({ name: "my-app", dependencies: { openai: "^4.0.0" } }, null, 2);
    const changes = buildPrFileChanges({
      callSites: oneCallSite,
      existingFiles: { "src/services/ai.ts": sampleTsContent, "package.json": pkgJson },
      repoFullName: "owner/repo",
      mode: "bidirectional",
    });
    const pkgChange = changes.find((c) => c.path === "package.json");
    expect(pkgChange).toBeDefined();
    const parsed: { dependencies: Record<string, string> } = JSON.parse(pkgChange?.content ?? "{}");
    expect(parsed.dependencies["@verum/sdk"]).toBe("latest");
    expect(parsed.dependencies["openai"]).toBe("^4.0.0");
  });

  it("bidirectional mode: skips package.json if @verum/sdk already present", () => {
    const pkgJson = JSON.stringify({ dependencies: { "@verum/sdk": "^1.0.0" } }, null, 2);
    const changes = buildPrFileChanges({
      callSites: oneCallSite,
      existingFiles: { "src/services/ai.ts": sampleTsContent, "package.json": pkgJson },
      repoFullName: "owner/repo",
      mode: "bidirectional",
    });
    expect(changes.find((c) => c.path === "package.json")).toBeUndefined();
  });

  it("bidirectional mode: skips package.json if it is malformed JSON", () => {
    const changes = buildPrFileChanges({
      callSites: oneCallSite,
      existingFiles: { "src/services/ai.ts": sampleTsContent, "package.json": "{ not valid json" },
      repoFullName: "owner/repo",
      mode: "bidirectional",
    });
    expect(changes.find((c) => c.path === "package.json")).toBeUndefined();
    // Import line should still be added despite malformed package.json
    expect(changes.find((c) => c.path === "src/services/ai.ts")).toBeDefined();
  });

  it("bidirectional mode: adds verum to requirements.txt for Python files", () => {
    const reqTxt = "openai>=1.0.0\nhttpx\n";
    const changes = buildPrFileChanges({
      callSites: [{ file_path: "src/service.py", line: 3, sdk: "openai", function: "create", prompt_ref: null }],
      existingFiles: { "src/service.py": samplePyContent, "requirements.txt": reqTxt },
      repoFullName: "owner/repo",
      mode: "bidirectional",
    });
    const reqChange = changes.find((c) => c.path === "requirements.txt");
    expect(reqChange).toBeDefined();
    expect(reqChange?.content).toContain("verum");
    expect(reqChange?.content).toContain("openai>=1.0.0");
  });

  it("bidirectional mode: skips requirements.txt if verum already present", () => {
    const reqTxt = "openai>=1.0.0\nverum\n";
    const changes = buildPrFileChanges({
      callSites: [{ file_path: "src/service.py", line: 3, sdk: "openai", function: "create", prompt_ref: null }],
      existingFiles: { "src/service.py": samplePyContent, "requirements.txt": reqTxt },
      repoFullName: "owner/repo",
      mode: "bidirectional",
    });
    expect(changes.find((c) => c.path === "requirements.txt")).toBeUndefined();
  });

  it("bidirectional mode: skips requirements.txt if file not in repo", () => {
    const changes = buildPrFileChanges({
      callSites: [{ file_path: "src/service.py", line: 3, sdk: "openai", function: "create", prompt_ref: null }],
      existingFiles: { "src/service.py": samplePyContent },
      repoFullName: "owner/repo",
      mode: "bidirectional",
    });
    expect(changes.find((c) => c.path === "requirements.txt")).toBeUndefined();
  });

  // ── insert-at-top fallback (no openai import present) ────────────────────

  it("bidirectional mode: inserts Python import at top when no openai import present", () => {
    const noImportPy = "client = some_lib.Client()\nclient.call()\n";
    const changes = buildPrFileChanges({
      callSites: [{ file_path: "src/service.py", line: 1, sdk: "openai", function: "create", prompt_ref: null }],
      existingFiles: { "src/service.py": noImportPy },
      repoFullName: "owner/repo",
      mode: "bidirectional",
    });
    const pyFile = changes.find((c) => c.path === "src/service.py");
    expect(pyFile).toBeDefined();
    const lines = pyFile!.content.split("\n");
    expect(lines[0]).toBe("import verum.openai");
  });

  it("bidirectional mode: inserts Python import after __future__ when no openai import present", () => {
    const futureOnlyPy = "from __future__ import annotations\nclient = some_lib.Client()\n";
    const changes = buildPrFileChanges({
      callSites: [{ file_path: "src/service.py", line: 2, sdk: "openai", function: "create", prompt_ref: null }],
      existingFiles: { "src/service.py": futureOnlyPy },
      repoFullName: "owner/repo",
      mode: "bidirectional",
    });
    const pyFile = changes.find((c) => c.path === "src/service.py");
    expect(pyFile).toBeDefined();
    const lines = pyFile!.content.split("\n");
    expect(lines[1]).toBe("import verum.openai");
  });

  it("bidirectional mode: inserts TS import at top when no openai import present", () => {
    const noImportTs = "const client = new SomeLib();\nclient.call();\n";
    const changes = buildPrFileChanges({
      callSites: [{ file_path: "src/service.ts", line: 1, sdk: "openai", function: "create", prompt_ref: null }],
      existingFiles: { "src/service.ts": noImportTs },
      repoFullName: "owner/repo",
      mode: "bidirectional",
    });
    const tsFile = changes.find((c) => c.path === "src/service.ts");
    expect(tsFile).toBeDefined();
    const lines = tsFile!.content.split("\n");
    expect(lines[0]).toBe('import "@verum/sdk/openai";');
  });
});
