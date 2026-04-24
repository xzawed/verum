"use client";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body>
        <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-8 text-center">
          <h1 className="text-2xl font-semibold">Critical error</h1>
          <p className="max-w-md text-sm text-gray-500">
            {error.message || "A critical error occurred. Please refresh the page."}
          </p>
          {error.digest && (
            <p className="font-mono text-xs text-gray-400">Error ID: {error.digest}</p>
          )}
          <button
            onClick={reset}
            className="rounded-md bg-gray-900 px-4 py-2 text-sm text-white hover:bg-gray-700"
          >
            Reload
          </button>
        </div>
      </body>
    </html>
  );
}
