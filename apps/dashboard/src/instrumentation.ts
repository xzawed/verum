export async function register() {
  // Only run in the Node.js runtime (not Edge), and only once per process.
  if (process.env.NEXT_RUNTIME === "nodejs") {
    if (process.env.SKIP_PYTHON_WORKER === "1") {
      console.log("[instrumentation] SKIP_PYTHON_WORKER=1 — skipping alembic and Python worker");
      return;
    }
    const { execFile } = await import("node:child_process");
    const { promisify } = await import("node:util");
    const { resolve } = await import("node:path");

    const execFileAsync = promisify(execFile);

    const workerCwd =
      process.env.PYTHON_WORKER_CWD ??
      resolve(process.cwd(), "../../apps/api");
    const pythonBin = process.env.PYTHON_BIN ?? "python3";

    try {
      console.log("[alembic] running migrations…");
      // Use async execFile so the event loop stays unblocked (healthcheck can respond).
      const { stdout, stderr } = await execFileAsync(
        pythonBin,
        ["-m", "alembic", "upgrade", "head"],
        {
          cwd: workerCwd,
          env: { ...process.env, PYTHONUNBUFFERED: "1" },
        },
      );
      if (stdout) process.stdout.write(stdout);
      if (stderr) process.stderr.write(stderr);
      console.log("[alembic] migrations complete");
    } catch (err) {
      console.error("[alembic] migration failed:", err);
      console.error("[alembic] Cannot start server with a broken schema — exiting");
      process.exit(1);
    }

    const { startPythonWorker, stopPythonWorker } = await import("./worker/spawn");
    startPythonWorker();
    process.on("SIGTERM", () => {
      stopPythonWorker();
    });
  }
}
