import { VERUM_CLIENT_SOURCE, VERUM_ENV_ADDITIONS } from "./verum-inline";

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

const TS_EXTENSIONS = /\.(ts|tsx|js|jsx|mjs|cjs)$/;
const VERUM_TODO_MARKER = "// TODO: [Verum]";

function buildTodoCommentLines(sdk: string, fn: string): string[] {
  return [
    `${VERUM_TODO_MARKER} Wrap this ${sdk} call (${fn}) with VerumClient for A/B prompt optimization. See: https://verum.dev/docs/sdk-integration`,
  ];
}

export function buildPrFileChanges(opts: {
  callSites: LLMCallSite[];
  existingFiles: Record<string, string>;
  repoFullName: string;
}): FileChange[] {
  const { callSites, existingFiles } = opts;
  const changes: FileChange[] = [];

  // 1. Always add the inline Verum client
  changes.push({ path: "src/lib/verum/client.ts", content: VERUM_CLIENT_SOURCE + "\n" });

  // 2. Add/update .env.example (skip if VERUM_API_URL already present)
  const existingEnv = existingFiles[".env.example"] ?? "";
  if (!existingEnv.includes("VERUM_API_URL")) {
    const newEnv = existingEnv
      ? existingEnv.trimEnd() + "\n\n" + VERUM_ENV_ADDITIONS
      : VERUM_ENV_ADDITIONS;
    changes.push({ path: ".env.example", content: newEnv });
  }

  // 3. Insert TODO comments in TypeScript files with detected call sites
  const fileCallSites = new Map<string, LLMCallSite[]>();
  for (const site of callSites) {
    if (!TS_EXTENSIONS.test(site.file_path)) continue;
    const existing = fileCallSites.get(site.file_path) ?? [];
    existing.push(site);
    fileCallSites.set(site.file_path, existing);
  }

  for (const [filePath, sites] of fileCallSites) {
    const original = existingFiles[filePath];
    if (!original) continue;

    // Sort descending by line so we insert from bottom up — preserves line numbers for earlier inserts
    const sorted = [...sites].sort((a, b) => b.line - a.line);
    const lines = original.split("\n");

    for (const site of sorted) {
      const insertAt = site.line - 1; // convert 1-indexed to 0-indexed
      if (insertAt < 0 || insertAt >= lines.length) continue;
      // Skip if a TODO comment already precedes this line (idempotent)
      if (lines[insertAt - 1]?.trimStart().startsWith(VERUM_TODO_MARKER)) continue;
      if (lines[insertAt - 2]?.trimStart().startsWith(VERUM_TODO_MARKER)) continue;
      if (lines[insertAt]?.trimStart().startsWith(VERUM_TODO_MARKER)) continue;
      const commentLines = buildTodoCommentLines(site.sdk, site.function);
      lines.splice(insertAt, 0, ...commentLines);
    }

    changes.push({ path: filePath, content: lines.join("\n") });
  }

  return changes;
}
