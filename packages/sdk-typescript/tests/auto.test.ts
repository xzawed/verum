/**
 * Tests for src/auto.ts — startup auto-patch module.
 *
 * Strategy: each test uses jest.resetModules() + manual require() so that
 * the module-level env-var checks run fresh under each env configuration.
 * The submodule imports (./openai, ./anthropic) are mocked to avoid real I/O.
 */

const OPENAI_MOD = "../src/openai.js";
const ANTHROPIC_MOD = "../src/anthropic.js";
const AUTO_MOD = "../src/auto.js";

function loadAuto(): void {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  require(AUTO_MOD);
}

beforeEach(() => {
  jest.resetModules();
  delete process.env["VERUM_API_URL"];
  delete process.env["VERUM_API_KEY"];
  delete process.env["VERUM_DISABLED"];
});

// ── no-op cases ─────────────────────────────────────────────────────────────

test("does not require submodules when env vars are absent", () => {
  jest.mock(OPENAI_MOD, () => {
    throw new Error("openai should not be required");
  });
  jest.mock(ANTHROPIC_MOD, () => {
    throw new Error("anthropic should not be required");
  });

  // Should not throw even though mocks throw on require
  expect(() => loadAuto()).not.toThrow();
});

test("does not require submodules when VERUM_DISABLED=1", () => {
  process.env["VERUM_DISABLED"] = "1";
  process.env["VERUM_API_URL"] = "https://verum.dev";
  process.env["VERUM_API_KEY"] = "key";

  jest.mock(OPENAI_MOD, () => {
    throw new Error("openai should not be required");
  });
  jest.mock(ANTHROPIC_MOD, () => {
    throw new Error("anthropic should not be required");
  });

  expect(() => loadAuto()).not.toThrow();
});

test("does not require submodules when VERUM_DISABLED=true", () => {
  process.env["VERUM_DISABLED"] = "true";
  process.env["VERUM_API_URL"] = "https://verum.dev";

  jest.mock(OPENAI_MOD, () => {
    throw new Error("openai should not be required");
  });
  jest.mock(ANTHROPIC_MOD, () => {
    throw new Error("anthropic should not be required");
  });

  expect(() => loadAuto()).not.toThrow();
});

test("does not require submodules when VERUM_DISABLED=yes", () => {
  process.env["VERUM_DISABLED"] = "yes";
  process.env["VERUM_API_URL"] = "https://verum.dev";

  jest.mock(OPENAI_MOD, () => {
    throw new Error("openai should not be required");
  });
  jest.mock(ANTHROPIC_MOD, () => {
    throw new Error("anthropic should not be required");
  });

  expect(() => loadAuto()).not.toThrow();
});

// ── patching cases ────────────────────────────────────────────────────────────

test("requires both submodules when VERUM_API_URL is set", () => {
  process.env["VERUM_API_URL"] = "https://verum.dev";

  const openaiLoaded = { called: false };
  const anthropicLoaded = { called: false };

  jest.mock(OPENAI_MOD, () => {
    openaiLoaded.called = true;
  });
  jest.mock(ANTHROPIC_MOD, () => {
    anthropicLoaded.called = true;
  });

  loadAuto();

  expect(openaiLoaded.called).toBe(true);
  expect(anthropicLoaded.called).toBe(true);
});

test("requires both submodules when VERUM_API_KEY is set (no URL)", () => {
  process.env["VERUM_API_KEY"] = "only-key";

  const openaiLoaded = { called: false };
  const anthropicLoaded = { called: false };

  jest.mock(OPENAI_MOD, () => {
    openaiLoaded.called = true;
  });
  jest.mock(ANTHROPIC_MOD, () => {
    anthropicLoaded.called = true;
  });

  loadAuto();

  expect(openaiLoaded.called).toBe(true);
  expect(anthropicLoaded.called).toBe(true);
});

// ── resilience ─────────────────────────────────────────────────────────────

test("swallows require error from missing openai package", () => {
  process.env["VERUM_API_URL"] = "https://verum.dev";

  jest.mock(OPENAI_MOD, () => {
    throw new Error("Cannot find module 'openai'");
  });
  jest.mock(ANTHROPIC_MOD, () => {
    // anthropic loads fine
  });

  expect(() => loadAuto()).not.toThrow();
});

test("swallows require error from missing anthropic package", () => {
  process.env["VERUM_API_URL"] = "https://verum.dev";

  jest.mock(OPENAI_MOD, () => {
    // openai loads fine
  });
  jest.mock(ANTHROPIC_MOD, () => {
    throw new Error("Cannot find module '@anthropic-ai/sdk'");
  });

  expect(() => loadAuto()).not.toThrow();
});
