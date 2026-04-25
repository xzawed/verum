import type { Config } from "jest";

const config: Config = {
  preset: "ts-jest",
  testEnvironment: "node",
  roots: ["<rootDir>/src"],
  testMatch: ["**/__tests__/**/*.test.ts"],
  transform: {
    "^.+\\.tsx?$": [
      "ts-jest",
      {
        tsconfig: {
          module: "commonjs",
          moduleResolution: "node",
          esModuleInterop: true,
          strict: true,
          rootDir: "./src",
          ignoreDeprecations: "6.0",
        },
      },
    ],
  },
  moduleNameMapper: {
    "^@/(.*)$": "<rootDir>/src/$1",
  },
  collectCoverageFrom: [
    "src/**/*.ts",
    "!src/**/*.tsx",
    "!src/**/*.d.ts",
    "!src/**/__tests__/**",
    "!src/**/*.test.ts",
    "!src/instrumentation.ts",
    // Auth.js config — depends on Auth.js internals, not unit-testable
    "!src/auth.ts",
    "!src/auth.config.ts",
    "!src/proxy.ts",
    "!src/app/api/auth/**",
    // E2E test-bypass endpoint — not production code
    "!src/app/api/test/**",
    // Thin factory delegators — tested via createGetByIdHandler factory (mirrors sonar exclusions)
    "!src/app/api/v1/analyze/[id]/route.ts",
    "!src/app/api/v1/infer/[id]/route.ts",
    "!src/app/api/v1/generate/[id]/route.ts",
    "!src/app/api/v1/deploy/[id]/route.ts",
    // Drizzle ORM schema — declarative, mirrors Alembic exclusion (mirrors sonar exclusion)
    "!src/lib/db/schema.ts",
    // Infrastructure / glue — worker spawn, DB init, Redis init (need real services)
    "!src/worker/spawn.ts",
    "!src/lib/db/client.ts",
    "!src/lib/rateLimitRedis.ts",
    // React hooks — require browser environment (jsdom), covered by Playwright E2E
    "!src/hooks/**",
  ],
  coverageDirectory: "coverage",
  coverageReporters: ["text", "lcov", "json-summary"],
  coverageThreshold: {
    global: {
      branches: 78,
      functions: 90,
      lines: 90,
      statements: 88,
    },
  },
};

export default config;
