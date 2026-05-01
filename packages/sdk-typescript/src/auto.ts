/**
 * Auto-patch OpenAI and Anthropic clients at Node.js startup.
 *
 * Load via NODE_OPTIONS environment variable — no code changes to your service:
 *
 *   NODE_OPTIONS="--require @verum/sdk/auto"
 *
 * Required environment variables:
 *   VERUM_API_URL      Base URL of the Verum API.
 *   VERUM_API_KEY      Your Verum API key.
 *   VERUM_DEPLOYMENT_ID  Deployment UUID to route all LLM calls through.
 *
 * Optional:
 *   VERUM_DISABLED     Set to "1", "true", or "yes" to disable auto-patching.
 *
 * Integration steps (zero code changes to your service):
 *   1. Set the four environment variables above in your deployment platform.
 *   2. Add NODE_OPTIONS="--require @verum/sdk/auto" to your process environment.
 *   3. That's it — all OpenAI and Anthropic calls are intercepted automatically.
 */

const disabled = process.env["VERUM_DISABLED"] ?? "";
const isDisabled =
  disabled === "1" ||
  disabled.toLowerCase() === "true" ||
  disabled.toLowerCase() === "yes";

const apiUrl = process.env["VERUM_API_URL"] ?? "";
const apiKey = process.env["VERUM_API_KEY"] ?? "";
const configured = Boolean(apiUrl || apiKey);

if (!isDisabled && configured) {
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    require("./openai");
  } catch {
    // openai package not installed — silently skip
  }

  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    require("./anthropic");
  } catch {
    // anthropic package not installed — silently skip
  }
}

export {};
