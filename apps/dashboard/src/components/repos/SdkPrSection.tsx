"use client";

import { useState } from "react";
import { z } from "zod";

const SdkPrResponse = z.object({
  pr_url: z.string().optional(),
  pr_number: z.number().optional(),
  files_changed: z.number().optional(),
  error: z.string().optional(),
});

interface SdkPrSectionProps {
  repoId: string;
  existingPrUrl?: string | null;
  existingPrNumber?: number | null;
}

type State =
  | { type: "idle" }
  | { type: "loading" }
  | { type: "done"; prUrl: string; prNumber: number; filesChanged: number }
  | { type: "error"; message: string };

export function SdkPrSection({ repoId, existingPrUrl, existingPrNumber }: SdkPrSectionProps) {
  const [state, setState] = useState<State>(
    existingPrUrl && existingPrNumber
      ? { type: "done", prUrl: existingPrUrl, prNumber: existingPrNumber, filesChanged: 0 }
      : { type: "idle" },
  );

  async function handleCreate() {
    setState({ type: "loading" });
    try {
      const res = await fetch(`/api/repos/${repoId}/sdk-pr`, { method: "POST" });
      const raw: unknown = await res.json();
      const data = SdkPrResponse.parse(raw);
      if (!res.ok || !data.pr_url || !data.pr_number) {
        setState({ type: "error", message: data.error ?? `HTTP ${res.status}` });
        return;
      }
      setState({
        type: "done",
        prUrl: data.pr_url,
        prNumber: data.pr_number,
        filesChanged: data.files_changed ?? 0,
      });
    } catch (e) {
      setState({ type: "error", message: e instanceof Error ? e.message : "Unknown error" });
    }
  }

  return (
    <section className="rounded-lg border border-neutral-200 p-6 dark:border-neutral-800">
      <h2 className="mb-1 text-lg font-semibold">SDK Integration PR</h2>
      <p className="mb-4 text-sm text-neutral-500 dark:text-neutral-400">
        Automatically create a GitHub PR that adds the Verum inline client and marks every LLM call
        site with integration instructions.
      </p>

      {state.type === "idle" && (
        <button
          onClick={() => void handleCreate()}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
        >
          Create SDK PR
        </button>
      )}

      {state.type === "loading" && (
        <div role="status" className="flex items-center gap-2 text-sm text-neutral-500">
          <span
            aria-label="loading"
            className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-blue-500 border-t-transparent"
          />
          Creating PR on GitHub…
        </div>
      )}

      {state.type === "done" && (
        <div className="rounded-md bg-green-50 p-4 dark:bg-green-950">
          <p className="text-sm font-medium text-green-800 dark:text-green-200">
            PR #{state.prNumber} opened
            {state.filesChanged > 0 && (
              <span className="ml-2 font-normal text-green-600 dark:text-green-400">
                ({state.filesChanged} files)
              </span>
            )}
          </p>
          <a
            href={state.prUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-1 inline-block text-sm text-blue-600 underline hover:text-blue-800 dark:text-blue-400"
          >
            View PR on GitHub →
          </a>
        </div>
      )}

      {state.type === "error" && (
        <div className="rounded-md bg-red-50 p-4 dark:bg-red-950">
          <p className="text-sm text-red-800 dark:text-red-200">Failed: {state.message}</p>
          <button
            onClick={() => setState({ type: "idle" })}
            className="mt-2 text-xs text-red-600 underline hover:text-red-800 dark:text-red-400"
          >
            Try again
          </button>
        </div>
      )}
    </section>
  );
}
