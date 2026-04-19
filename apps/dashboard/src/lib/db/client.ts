import { drizzle } from "drizzle-orm/node-postgres";
import { Pool } from "pg";
import * as schema from "./schema";

let _db: ReturnType<typeof drizzle<typeof schema>> | null = null;

function getDb() {
  if (!_db) {
    const pool = new Pool({
      connectionString: process.env.DATABASE_URL ?? "postgresql://verum:verum@localhost:5432/verum",
      ssl:
        process.env.NODE_ENV === "production"
          ? { rejectUnauthorized: false }
          : false,
    });
    _db = drizzle(pool, { schema });
  }
  return _db;
}

export const db = new Proxy({} as ReturnType<typeof drizzle<typeof schema>>, {
  get(_target, prop) {
    return (getDb() as Record<string | symbol, unknown>)[prop];
  },
});
