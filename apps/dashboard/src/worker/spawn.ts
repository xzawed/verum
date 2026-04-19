import { spawn, type ChildProcess } from "node:child_process";
import { resolve } from "node:path";

let worker: ChildProcess | null = null;
let backoffMs = 1_000;
const MAX_BACKOFF = 30_000;

// In Docker the worker lives at /app/apps/api; in local dev, resolve relative to CWD.
const WORKER_CWD =
  process.env.PYTHON_WORKER_CWD ??
  resolve(process.cwd(), "../../apps/api");

const PYTHON_BIN = process.env.PYTHON_BIN ?? "python3";

export function startPythonWorker() {
  if (worker) return;

  worker = spawn(PYTHON_BIN, ["-m", "src.main"], {
    cwd: WORKER_CWD,
    env: { ...process.env, PYTHONUNBUFFERED: "1" },
    stdio: ["ignore", "inherit", "inherit"],
  });

  worker.on("spawn", () => {
    backoffMs = 1_000;
    console.log("[python-worker] started (pid=%d)", worker?.pid);
  });

  worker.on("error", (err) => {
    console.error("[python-worker] spawn error:", err.message);
  });

  worker.on("exit", (code, signal) => {
    console.error("[python-worker] exited code=%s signal=%s — respawning in %dms", code, signal, backoffMs);
    worker = null;
    setTimeout(() => {
      backoffMs = Math.min(backoffMs * 2, MAX_BACKOFF);
      startPythonWorker();
    }, backoffMs);
  });
}

export function stopPythonWorker() {
  if (worker) {
    worker.kill("SIGTERM");
    worker = null;
  }
}
