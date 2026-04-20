export async function register() {
  // Only run in the Node.js runtime (not Edge), and only once per process.
  if (process.env.NEXT_RUNTIME === "nodejs") {
    const { execFileSync } = await import("node:child_process");
    const { resolve } = await import("node:path");

    const workerCwd =
      process.env.PYTHON_WORKER_CWD ??
      resolve(process.cwd(), "../../apps/api");
    const pythonBin = process.env.PYTHON_BIN ?? "python3";

    try {
      console.log("[alembic] running migrations…");
      execFileSync(
        pythonBin,
        ["-m", "alembic", "upgrade", "head"],
        {
          cwd: workerCwd,
          env: { ...process.env, PYTHONUNBUFFERED: "1" },
          stdio: "inherit",
        },
      );
      console.log("[alembic] migrations complete");
    } catch (err) {
      console.error("[alembic] migration failed:", err);
      // Don't crash the server — the worker will fail on its own if the schema is wrong.
    }

    const { startPythonWorker, stopPythonWorker } = await import("./worker/spawn");
    startPythonWorker();
    process.on("SIGTERM", () => {
      stopPythonWorker();
    });
  }
}
