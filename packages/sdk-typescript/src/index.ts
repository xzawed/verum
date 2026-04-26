export { VerumClient } from "./client.js";
export type { ChatMessage } from "./client.js";

export { SafeConfigResolver } from "./_safe-resolver.js";
export type { DeploymentConfig, ResolveReason, ResolveResult } from "./_safe-resolver.js";

export { patchOpenAI } from "./openai.js";
export { patchAnthropic } from "./anthropic.js";

// ── Top-level convenience functions ──────────────────────────────────────────
// These mirror the Python SDK's module-level API so callers do not need
// to instantiate VerumClient themselves.

import { VerumClient } from "./client.js";

let _client: VerumClient | null = null;
function _getClient(): VerumClient {
  if (!_client) _client = new VerumClient();
  return _client;
}

/** Retrieve knowledge chunks from the Verum RAG index.
 *  Convenience wrapper — equivalent to `new VerumClient().retrieve(...)`.
 */
export async function retrieve(params: {
  query: string;
  collectionName: string;
  topK?: number;
}): Promise<Array<{ content: string; [key: string]: unknown }>> {
  return _getClient().retrieve(params);
}

/** Record user feedback for a trace.
 *  Convenience wrapper — equivalent to `new VerumClient().feedback(...)`.
 */
export async function feedback(params: {
  traceId: string;
  score: 1 | -1;
}): Promise<void> {
  return _getClient().feedback(params);
}
