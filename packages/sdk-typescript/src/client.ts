import { DeploymentConfigCache } from "./cache.js";
import { chooseVariant } from "./router.js";

export interface ChatMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

interface DeploymentConfig {
  deployment_id: string;
  status: string;
  traffic_split: number;
  variant_prompt: string | null;
}

interface ChatParams {
  messages: ChatMessage[];
  deploymentId?: string;
  provider?: "openai" | "anthropic" | "grok";
  model: string;
  [key: string]: unknown;
}

interface ChatResult {
  messages: ChatMessage[];
  routed_to: "variant" | "baseline";
  deployment_id: string | null;
}

interface RetrieveParams {
  query: string;
  collectionName: string;
  topK?: number;
}

interface Chunk {
  content: string;
  [key: string]: unknown;
}

interface FeedbackParams {
  traceId: string;
  score: 1 | -1;
}

export class VerumClient {
  private readonly apiUrl: string;
  private readonly apiKey: string;
  private readonly cache: DeploymentConfigCache<DeploymentConfig>;

  constructor(options?: { apiUrl?: string; apiKey?: string; cacheTtlMs?: number }) {
    this.apiUrl = (options?.apiUrl ?? process.env["VERUM_API_URL"] ?? "").replace(/\/$/, "");
    this.apiKey = options?.apiKey ?? process.env["VERUM_API_KEY"] ?? "";
    this.cache = new DeploymentConfigCache(options?.cacheTtlMs ?? 60_000);
  }

  async chat(params: ChatParams): Promise<ChatResult> {
    const { messages, deploymentId } = params;

    if (!deploymentId) {
      return { messages, routed_to: "baseline", deployment_id: null };
    }

    const config = await this.getDeploymentConfig(deploymentId);
    const routedTo = chooseVariant(config.traffic_split);
    let finalMessages = [...messages];

    if (routedTo === "variant" && config.variant_prompt) {
      if (finalMessages[0]?.role === "system") {
        finalMessages[0] = { ...finalMessages[0], content: config.variant_prompt };
      } else {
        finalMessages = [{ role: "system", content: config.variant_prompt }, ...finalMessages];
      }
    }

    return { messages: finalMessages, routed_to: routedTo, deployment_id: deploymentId };
  }

  async retrieve(params: RetrieveParams): Promise<Chunk[]> {
    const res = await fetch(`${this.apiUrl}/api/v1/retrieve-sdk`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-verum-api-key": this.apiKey },
      body: JSON.stringify({
        query: params.query,
        collection_name: params.collectionName,
        top_k: params.topK ?? 5,
      }),
    });
    if (!res.ok) throw new Error(`retrieve failed: ${res.status}`);
    const data = await res.json() as { chunks: Chunk[] };
    return data.chunks;
  }

  async feedback(params: FeedbackParams): Promise<void> {
    const res = await fetch(`${this.apiUrl}/api/v1/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-verum-api-key": this.apiKey },
      body: JSON.stringify({ trace_id: params.traceId, score: params.score }),
    });
    if (!res.ok) throw new Error(`feedback failed: ${res.status}`);
  }

  private async getDeploymentConfig(deploymentId: string): Promise<DeploymentConfig> {
    const cached = this.cache.get(deploymentId);
    if (cached) return cached;

    const res = await fetch(`${this.apiUrl}/api/v1/deploy/${deploymentId}/config`, {
      headers: { "x-verum-api-key": this.apiKey },
    });
    if (!res.ok) throw new Error(`config fetch failed: ${res.status}`);
    const config = await res.json() as DeploymentConfig;
    this.cache.set(deploymentId, config);
    return config;
  }
}
