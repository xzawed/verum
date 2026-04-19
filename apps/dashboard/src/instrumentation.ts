export async function register() {
  // Only run in the Node.js runtime (not Edge), and only once per process.
  if (process.env.NEXT_RUNTIME === "nodejs") {
    const { startPythonWorker, stopPythonWorker } = await import("./worker/spawn");
    startPythonWorker();
    process.on("SIGTERM", () => {
      stopPythonWorker();
    });
  }
}
