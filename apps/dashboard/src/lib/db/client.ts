import { drizzle } from "drizzle-orm/node-postgres";
import { Pool } from "pg";
import * as schema from "./schema";

let _db: ReturnType<typeof drizzle<typeof schema>> | null = null;

// DATABASE_URL is validated lazily in getDb() so that `next build` can import
// this module without a database connection present in the build environment.
// The throw fires on the first actual query attempt, not at module load time.
function getDb() {
  if (!_db) {
    const dbUrl = process.env.DATABASE_URL;
    if (!dbUrl) {
      throw new Error(
        "DATABASE_URL environment variable is required. " +
        "Set it to a valid PostgreSQL connection string before starting the application."
      );
    }
    // Supabase Connection Pooler (Supavisor) uses a self-signed certificate chain.
    // ssl:true triggers pg's full chain verification which fails; rejectUnauthorized:false
    // keeps the connection encrypted while skipping chain verification.
    // DB_SSL=disable overrides for Docker/integration environments where Postgres
    // has no SSL configured and the SSLRequest would be rejected.
    const wantSsl =
      process.env.DB_SSL !== "disable" && process.env.NODE_ENV === "production";
    const pool = new Pool({
      connectionString: dbUrl,
      ssl: wantSsl ? { rejectUnauthorized: false } : false,
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
