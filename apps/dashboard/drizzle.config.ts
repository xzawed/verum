import type { Config } from "drizzle-kit";

export default {
  out: "./src/lib/db/schema",
  dialect: "postgresql",
  dbCredentials: {
    url: process.env.DATABASE_URL ?? "postgresql://verum:verum@localhost:5432/verum",
  },
} satisfies Config;
