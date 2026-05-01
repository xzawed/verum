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

const TS_EXTENSIONS = /\.(ts|tsx|js|jsx|mjs|cjs)$/;
const VERUM_IN_REQUIREMENTS = /^\s*verum\b/m;

function isPyFile(path: string): boolean {
  return path.endsWith(".py");
}

function isTsFile(path: string): boolean {
  return TS_EXTENSIONS.test(path);
}

// ── Insert-line finders ───────────────────────────────────────────────────────

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

// ── Per-file change builders ──────────────────────────────────────────────────

function buildEnvChange(existingFiles: Record<string, string>): FileChange | null {
  const existing = existingFiles[".env.example"] ?? "";
  if (existing.includes("VERUM_API_URL")) return null;
  const content = existing
    ? existing.trimEnd() + "\n\n" + VERUM_ENV_ADDITIONS
    : VERUM_ENV_ADDITIONS;
  return { path: ".env.example", content };
}

function buildPackageJsonChange(existingFiles: Record<string, string>): FileChange | null {
  const raw = existingFiles["package.json"];
  if (!raw || raw.includes("@verum/sdk")) return null;
  try {
    const pkg = JSON.parse(raw) as Record<string, unknown>;
    const deps = (pkg["dependencies"] ?? {}) as Record<string, string>;
    deps["@verum/sdk"] = "latest";
    pkg["dependencies"] = deps;
    return { path: "package.json", content: JSON.stringify(pkg, null, 2) + "\n" };
  } catch {
    // malformed package.json — skip, import line will still be added
    return null;
  }
}

function buildRequirementsChange(existingFiles: Record<string, string>): FileChange | null {
  const raw = existingFiles["requirements.txt"];
  if (raw === undefined || VERUM_IN_REQUIREMENTS.exec(raw)) return null;
  return { path: "requirements.txt", content: raw.trimEnd() + "\nverum\n" };
}

function buildImportChange(filePath: string, original: string): FileChange | null {
  const isPython = isPyFile(filePath);
  const marker = isPython ? "import verum.openai" : "@verum/sdk/openai";
  if (original.includes(marker)) return null;

  const verumImport = isPython ? "import verum.openai" : 'import "@verum/sdk/openai";';
  const lines = original.split("\n");
  const insertAt = isPython ? findPythonInsertLine(lines) : findTsInsertLine(lines);
  lines.splice(insertAt, 0, verumImport);
  return { path: filePath, content: lines.join("\n") };
}

// ── Path normalization ────────────────────────────────────────────────────────

function normalizePath(p: string): string {
  // GitHub Git Trees API requires forward slashes and rejects absolute paths or traversals.
  return p.replace(/\\/g, "/");
}

function isSafePath(p: string): boolean {
  const normalized = normalizePath(p);
  return (
    !normalized.startsWith("/") &&
    !normalized.split("/").some((seg) => seg === "..")
  );
}

// ── Main export ───────────────────────────────────────────────────────────────

export function buildPrFileChanges(opts: {
  readonly callSites: LLMCallSite[];
  readonly existingFiles: Record<string, string>;
  readonly repoFullName: string;
  readonly mode: PrMode;
}): FileChange[] {
  const { callSites, existingFiles, mode } = opts;
  const changes: FileChange[] = [];

  const envChange = buildEnvChange(existingFiles);
  if (envChange) changes.push(envChange);

  if (mode === "observe") return changes;

  // Group call sites by file; track which language types are present
  const fileCallSites = new Map<string, LLMCallSite[]>();
  let hasPyCallSites = false;
  let hasTsCallSites = false;
  for (const site of callSites) {
    const filePath = normalizePath(site.file_path);
    if (!isSafePath(filePath)) continue;
    if (isPyFile(filePath)) {
      hasPyCallSites = true;
    } else if (isTsFile(filePath)) {
      hasTsCallSites = true;
    } else {
      continue;
    }
    const group = fileCallSites.get(filePath) ?? [];
    group.push({ ...site, file_path: filePath });
    fileCallSites.set(filePath, group);
  }

  if (hasTsCallSites) {
    const pkgChange = buildPackageJsonChange(existingFiles);
    if (pkgChange) changes.push(pkgChange);
  }
  if (hasPyCallSites) {
    const reqChange = buildRequirementsChange(existingFiles);
    if (reqChange) changes.push(reqChange);
  }

  for (const [filePath] of fileCallSites) {
    const original = existingFiles[filePath] ?? existingFiles[filePath.replaceAll("/", "\\")];
    if (!original) continue;
    const importChange = buildImportChange(filePath, original);
    if (importChange) changes.push(importChange);
  }

  return changes;
}
