export interface LLMCallSite {
  file_path: string;
  line: number;
  sdk: string;
  function: string;
  prompt_ref: string | null;
}

export interface FileChange {
  path: string;
  content: string;
}

export type PrMode = "observe" | "bidirectional";

// ── Env vars appended in both modes ──────────────────────────────────────────

const VERUM_ENV_ADDITIONS = `# Verum observability (Phase 0 — OTLP only)
OTEL_EXPORTER_OTLP_ENDPOINT=https://verum-production.up.railway.app/api/v1/otlp
OTEL_EXPORTER_OTLP_HEADERS=Authorization=Bearer YOUR_VERUM_API_KEY
VERUM_API_URL=https://verum-production.up.railway.app
VERUM_API_KEY=YOUR_VERUM_API_KEY
VERUM_DEPLOYMENT_ID=YOUR_DEPLOYMENT_ID
`;

// ── Helpers ───────────────────────────────────────────────────────────────────

const PY_EXTENSIONS = /\.py$/;
const TS_EXTENSIONS = /\.(ts|tsx|js|jsx|mjs|cjs)$/;

/**
 * Returns the 0-indexed line number just *after* the last `import openai` /
 * `from openai` block in a Python file, or 0 if none found.
 * Also skips past any leading `from __future__` imports.
 */
function findPythonInsertLine(lines: string[]): number {
  let lastOpenaiImport = -1;
  let lastFutureImport = -1;

  for (let i = 0; i < lines.length; i++) {
    const trimmed = lines[i].trimStart();
    if (trimmed.startsWith("from __future__") || trimmed.startsWith("import __future__")) {
      lastFutureImport = i;
    }
    if (trimmed.startsWith("import openai") || trimmed.startsWith("from openai")) {
      lastOpenaiImport = i;
    }
  }

  if (lastOpenaiImport >= 0) return lastOpenaiImport + 1;
  if (lastFutureImport >= 0) return lastFutureImport + 1;
  return 0;
}

/**
 * Returns the 0-indexed line number just *after* the last `from "openai"` /
 * `require("openai")` / `from 'openai'` line in a TS/JS file, or 0 if none.
 */
function findTsInsertLine(lines: string[]): number {
  let lastOpenaiImport = -1;

  for (let i = 0; i < lines.length; i++) {
    const trimmed = lines[i].trimStart();
    if (
      /^import\s.*["']openai["']/.test(trimmed) ||
      /^import\s+["']openai["']/.test(trimmed) ||
      /require\(["']openai["']\)/.test(trimmed)
    ) {
      lastOpenaiImport = i;
    }
  }

  return lastOpenaiImport >= 0 ? lastOpenaiImport + 1 : 0;
}

// ── Main export ───────────────────────────────────────────────────────────────

export function buildPrFileChanges(opts: {
  callSites: LLMCallSite[];
  existingFiles: Record<string, string>;
  repoFullName: string;
  mode: PrMode;
}): FileChange[] {
  const { callSites, existingFiles, mode } = opts;
  const changes: FileChange[] = [];

  // ── 1. Always update .env.example ──────────────────────────────────────────
  const existingEnv = existingFiles[".env.example"] ?? "";
  if (!existingEnv.includes("VERUM_API_URL")) {
    const newEnv = existingEnv
      ? existingEnv.trimEnd() + "\n\n" + VERUM_ENV_ADDITIONS
      : VERUM_ENV_ADDITIONS;
    changes.push({ path: ".env.example", content: newEnv });
  }

  // ── 2. observe mode: env only, nothing else ─────────────────────────────────
  if (mode === "observe") return changes;

  // ── 3. bidirectional mode: insert one-line import per affected file ─────────
  const fileCallSites = new Map<string, LLMCallSite[]>();
  for (const site of callSites) {
    if (!PY_EXTENSIONS.test(site.file_path) && !TS_EXTENSIONS.test(site.file_path)) continue;
    const existing = fileCallSites.get(site.file_path) ?? [];
    existing.push(site);
    fileCallSites.set(site.file_path, existing);
  }

  for (const [filePath] of fileCallSites) {
    const original = existingFiles[filePath];
    if (!original) continue;

    const isPython = PY_EXTENSIONS.test(filePath);
    const verum_import = isPython ? "import verum.openai" : 'import "@verum/sdk/openai";';
    const already_present_pattern = isPython ? "import verum.openai" : "@verum/sdk/openai";

    // Idempotent: skip if the import already exists
    if (original.includes(already_present_pattern)) continue;

    const lines = original.split("\n");
    const insertAt = isPython ? findPythonInsertLine(lines) : findTsInsertLine(lines);
    lines.splice(insertAt, 0, verum_import);

    changes.push({ path: filePath, content: lines.join("\n") });
  }

  return changes;
}
