import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { getDatabaseUrl, requiresPhase2Database } from "./database.js";
import { getPool, pingDatabase } from "./pool.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/**
 * @throws {Error}
 */
export function assertDatabaseConfigured() {
  if (!requiresPhase2Database()) {
    return;
  }
  if (!getDatabaseUrl()) {
    throw new Error(
      "DATABASE_URL is required when MOVIE_TELLER_RUN_MODE is api or worker (Phase 2 Lite)"
    );
  }
}

export async function runMigrations() {
  const migrationsDir = path.resolve(__dirname, "../../db/migrations");
  const pool = getPool();
  const client = await pool.connect();
  try {
    await client.query("SELECT pg_advisory_lock(771981001)");
    await client.query(`
      CREATE TABLE IF NOT EXISTS schema_migrations (
        name TEXT PRIMARY KEY,
        applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
      )
    `);
    const files = fs
      .readdirSync(migrationsDir)
      .filter((name) => name.endsWith(".sql"))
      .sort();
    for (const file of files) {
      const applied = await client.query(
        "SELECT 1 FROM schema_migrations WHERE name = $1",
        [file]
      );
      if (applied.rowCount > 0) continue;
      const sql = fs.readFileSync(path.join(migrationsDir, file), "utf8");
      try {
        await client.query("BEGIN");
        await client.query(sql);
        await client.query("INSERT INTO schema_migrations (name) VALUES ($1)", [file]);
        await client.query("COMMIT");
        console.log(`[db] applied migration ${file}`);
      } catch (err) {
        await client.query("ROLLBACK");
        throw err;
      }
    }
  } finally {
    try {
      await client.query("SELECT pg_advisory_unlock(771981001)");
    } finally {
      client.release();
    }
  }
}

export async function ensureDatabaseReady() {
  assertDatabaseConfigured();
  const url = getDatabaseUrl();
  if (!url) return;
  await pingDatabase();
  await runMigrations();
}
