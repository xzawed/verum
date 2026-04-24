"use client";

import { useEffect, useRef } from "react";

interface Options {
  /** Fastest interval — used when the job is active (default 2 s). */
  minIntervalMs?: number;
  /** Slowest interval — ceiling when the job is stable (default 30 s). */
  maxIntervalMs?: number;
  /** Multiplier applied to the interval after each stable poll (default 2). */
  backoffFactor?: number;
}

/**
 * Polls `fetchFn` on an adaptive schedule:
 * - Resets to `minIntervalMs` whenever `isActive` is true (job running/pending).
 * - Exponentially backs off toward `maxIntervalMs` when `isActive` is false.
 *
 * Replaces fixed-interval `setInterval` calls in client components that poll
 * job status endpoints.
 */
export function useAdaptivePolling(
  fetchFn: () => Promise<void>,
  isActive: boolean,
  {
    minIntervalMs = 2_000,
    maxIntervalMs = 30_000,
    backoffFactor = 2,
  }: Options = {},
): void {
  // Keep always-current references to avoid stale closures in the timer.
  const fetchRef = useRef(fetchFn);
  const isActiveRef = useRef(isActive);
  const intervalMs = useRef(minIntervalMs);
  const cancelled = useRef(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Sync refs on every render (cheap, avoids re-running the main effect).
  useEffect(() => {
    fetchRef.current = fetchFn;
  });

  useEffect(() => {
    isActiveRef.current = isActive;
    // Reset to fast polling as soon as the caller signals activity.
    if (isActive) {
      intervalMs.current = minIntervalMs;
    }
  }, [isActive, minIntervalMs]);

  useEffect(() => {
    cancelled.current = false;
    intervalMs.current = minIntervalMs;

    const tick = async (): Promise<void> => {
      if (cancelled.current) return;
      await fetchRef.current();
      if (cancelled.current) return;

      if (isActiveRef.current) {
        intervalMs.current = minIntervalMs;
      } else {
        intervalMs.current = Math.min(
          intervalMs.current * backoffFactor,
          maxIntervalMs,
        );
      }

      timer.current = setTimeout(() => void tick(), intervalMs.current);
    };

    timer.current = setTimeout(() => void tick(), intervalMs.current);

    return () => {
      cancelled.current = true;
      if (timer.current !== null) {
        clearTimeout(timer.current);
        timer.current = null;
      }
    };
  // Only re-create the timer loop when static options change.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [minIntervalMs, maxIntervalMs, backoffFactor]);
}
