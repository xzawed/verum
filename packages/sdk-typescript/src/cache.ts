interface CacheEntry<T> {
  value: T;
  freshExpiresAt: number;
  staleExpiresAt: number;
}

export class DeploymentConfigCache<T = unknown> {
  private store = new Map<string, CacheEntry<T>>();

  constructor(
    private readonly ttlMs: number = 60_000,
    private readonly staleTtlMs: number = 86_400_000,
  ) {}

  /** Returns the value only if within the fresh TTL window. */
  getFresh(key: string): T | undefined {
    const entry = this.store.get(key);
    if (!entry) return undefined;
    if (Date.now() > entry.freshExpiresAt) return undefined;
    return entry.value;
  }

  /** Returns the value if within the stale TTL window (even if fresh has expired). */
  getStale(key: string): T | undefined {
    const entry = this.store.get(key);
    if (!entry) return undefined;
    if (Date.now() > entry.staleExpiresAt) {
      this.store.delete(key);
      return undefined;
    }
    return entry.value;
  }

  /** Backward-compatible alias for getFresh. */
  get(key: string): T | undefined {
    return this.getFresh(key);
  }

  set(key: string, value: T): void {
    const now = Date.now();
    this.store.set(key, {
      value,
      freshExpiresAt: now + this.ttlMs,
      staleExpiresAt: now + this.staleTtlMs,
    });
  }
}
