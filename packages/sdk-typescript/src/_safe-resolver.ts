import { DeploymentConfigCache } from "./cache.js";
import { chooseVariant } from "./router.js";

export interface DeploymentConfig {
  traffic_split: number;
  variant_prompt: string | null;
}

export type ResolveReason = "fresh" | "fetched" | "stale" | "circuit_open" | "fail_open";

export interface ResolveResult {
  messages: Array<{ role: string; content: string }>;
  reason: ResolveReason;
}

export class SafeConfigResolver {
  private failureCount = 0;
  private circuitOpenUntil = 0;
  private readonly FAILURE_THRESHOLD = 5;
  private readonly CIRCUIT_OPEN_MS = 300_000;
  private readonly FETCH_TIMEOUT_MS = 200;

  constructor(
    private readonly apiUrl: string,
    private readonly apiKey: string,
    private readonly cache: DeploymentConfigCache<DeploymentConfig>,
  ) {}

  async resolve(
    deploymentId: string,
    fallbackMessages: Array<{ role: string; content: string }>,
  ): Promise<ResolveResult> {
    // 1. Circuit breaker open → fail open immediately
    if (Date.now() < this.circuitOpenUntil) {
      return { messages: fallbackMessages, reason: "circuit_open" };
    }

    // 2. Fresh cache hit
    const fresh = this.cache.getFresh(deploymentId);
    if (fresh) {
      return { messages: this._applyConfig(fresh, fallbackMessages), reason: "fresh" };
    }

    // 3. Try to fetch with 200ms timeout
    let fetched: DeploymentConfig | null = null;
    try {
      fetched = await this._fetchConfig(deploymentId);
      this.cache.set(deploymentId, fetched);
      this.failureCount = 0;
      return { messages: this._applyConfig(fetched, fallbackMessages), reason: "fetched" };
    } catch {
      this.failureCount++;
      if (this.failureCount >= this.FAILURE_THRESHOLD) {
        this.circuitOpenUntil = Date.now() + this.CIRCUIT_OPEN_MS;
      }
    }

    // 4. Stale cache hit
    const stale = this.cache.getStale(deploymentId);
    if (stale) {
      return { messages: this._applyConfig(stale, fallbackMessages), reason: "stale" };
    }

    // 5. Fail open — use original messages unchanged
    return { messages: fallbackMessages, reason: "fail_open" };
  }

  private async _fetchConfig(deploymentId: string): Promise<DeploymentConfig> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.FETCH_TIMEOUT_MS);
    try {
      const res = await fetch(
        `${this.apiUrl}/api/v1/deploy/${deploymentId}/config`,
        {
          headers: { "x-verum-api-key": this.apiKey },
          signal: controller.signal,
        },
      );
      if (!res.ok) throw new Error(`config fetch failed: ${res.status}`);
      return (await res.json()) as DeploymentConfig;
    } finally {
      clearTimeout(timer);
    }
  }

  _applyConfig(
    config: DeploymentConfig,
    messages: Array<{ role: string; content: string }>,
  ): Array<{ role: string; content: string }> {
    if (chooseVariant(config.traffic_split) !== "variant" || !config.variant_prompt) {
      return messages;
    }

    const variantPrompt = config.variant_prompt;
    const firstSystemIdx = messages.findIndex((m) => m.role === "system");
    if (firstSystemIdx !== -1) {
      return messages.map((m, i) =>
        i === firstSystemIdx ? { ...m, content: variantPrompt } : m,
      );
    }
    // No system message — prepend one
    return [{ role: "system", content: variantPrompt }, ...messages];
  }
}
