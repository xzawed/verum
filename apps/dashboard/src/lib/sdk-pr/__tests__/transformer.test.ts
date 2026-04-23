import { buildPrFileChanges } from "../transformer";
import type { LLMCallSite } from "../transformer";

const oneCallSite: LLMCallSite[] = [
  { file_path: "src/services/ai.ts", line: 5, sdk: "openai", function: "chat.completions.create", prompt_ref: null },
];

const sampleFileContent = [
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

describe("buildPrFileChanges", () => {
  it("always includes src/lib/verum/client.ts", () => {
    const changes = buildPrFileChanges({ callSites: [], existingFiles: {}, repoFullName: "owner/repo" });
    const clientFile = changes.find((c) => c.path === "src/lib/verum/client.ts");
    expect(clientFile).toBeDefined();
    expect(clientFile!.content).toContain("class VerumClient");
  });

  it("creates .env.example when it does not exist", () => {
    const changes = buildPrFileChanges({ callSites: [], existingFiles: {}, repoFullName: "owner/repo" });
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
    });
    const envFile = changes.find((c) => c.path === ".env.example");
    expect(envFile).toBeUndefined();
  });

  it("inserts TODO comment above the detected call site line", () => {
    const changes = buildPrFileChanges({
      callSites: oneCallSite,
      existingFiles: { "src/services/ai.ts": sampleFileContent },
      repoFullName: "owner/repo",
    });
    const aiFile = changes.find((c) => c.path === "src/services/ai.ts");
    expect(aiFile).toBeDefined();
    const lines = aiFile!.content.split("\n");
    const todoIdx = lines.findIndex((l) => l.includes("// TODO: [Verum]"));
    expect(todoIdx).toBeGreaterThanOrEqual(0);
    expect(lines[todoIdx + 1]).toContain("client.chat.completions.create");
  });

  it("does not insert duplicate TODO comments when called twice", () => {
    const firstPass = buildPrFileChanges({
      callSites: oneCallSite,
      existingFiles: { "src/services/ai.ts": sampleFileContent },
      repoFullName: "owner/repo",
    });
    const modified = firstPass.find((c) => c.path === "src/services/ai.ts")!.content;
    const secondPass = buildPrFileChanges({
      callSites: oneCallSite,
      existingFiles: { "src/services/ai.ts": modified },
      repoFullName: "owner/repo",
    });
    const finalFile = secondPass.find((c) => c.path === "src/services/ai.ts")!;
    const count = (finalFile.content.match(/\/\/ TODO: \[Verum\]/g) ?? []).length;
    expect(count).toBe(1);
  });

  it("skips non-TypeScript files in call_sites", () => {
    const changes = buildPrFileChanges({
      callSites: [{ file_path: "src/script.py", line: 3, sdk: "openai", function: "create", prompt_ref: null }],
      existingFiles: { "src/script.py": "import openai\nclient = openai.OpenAI()\nclient.chat.completions.create()\n" },
      repoFullName: "owner/repo",
    });
    const pyFile = changes.find((c) => c.path === "src/script.py");
    expect(pyFile).toBeUndefined();
  });
});
