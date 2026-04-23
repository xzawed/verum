import { drizzle } from "drizzle-orm/node-postgres";
import { Pool } from "pg";
import * as schema from "./schema";

let _db: ReturnType<typeof drizzle<typeof schema>> | null = null;

/**
 * Validate DATABASE_URL on module load.
 *
 * Throws immediately if DATABASE_URL is not set in any environment.
 * This prevents misconfigured deployments from silently using insecure
 * hardcoded credentials.
 */
const dbUrl = process.env.DATABASE_URL;
if (!dbUrl) {
  throw new Error(
    "DATABASE_URL environment variable is required. " +
    "Set it to a valid PostgreSQL connection string before starting the application."
  );
}

function getDb() {
  if (!_db) {
    const pool = new Pool({
      connectionString: dbUrl,
      ssl:
        process.env.NODE_ENV === "production"
          ? true
          : false,
    });
    _db = drizzle(pool, { schema });
  }
  return _db;
}

export const db = new Proxy({} as ReturnType<typeof drizzle<typeof schema>>, {
  get(_target, prop) {
    return (getDb() as unknown as Record<string | symbol, unknown>)[prop];
  },
});
