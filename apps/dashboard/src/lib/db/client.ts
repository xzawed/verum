import { drizzle } from "drizzle-orm/node-postgres";
import { sql } from "drizzle-orm";
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

/**
 * Execute fn inside a transaction with app.current_user_id set for RLS.
 *
 * Uses set_config(..., true) (transaction-scoped) so the GUC resets
 * automatically when the transaction commits or rolls back.  Once
 * migration 0022 (FORCE ROW LEVEL SECURITY) is applied and the app
 * connects as verum_app, this context activates per-user row filtering.
 *
 * @example
 *   const result = await withUserId(session.user.id, (tx) =>
 *     tx.select().from(schema.repos).where(eq(schema.repos.ownerUserId, uid))
 *   );
 */
export async function withUserId<T>(
  userId: string,
  fn: (tx: ReturnType<typeof drizzle<typeof schema>>) => Promise<T>,
): Promise<T> {
  return getDb().transaction(async (tx) => {
    await tx.execute(sql`SELECT set_config('app.current_user_id', ${userId}, true)`);
    return fn(tx as unknown as ReturnType<typeof drizzle<typeof schema>>);
  });
}
