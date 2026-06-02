import pg from "pg";

import { getDatabaseUrl } from "./database.js";

/** @type {pg.Pool | null} */
let pool = null;

/**
 * @returns {pg.Pool}
 */
export function getPool() {
  const url = getDatabaseUrl();
  if (!url) {
    throw new Error("DATABASE_URL is not configured");
  }
  if (!pool) {
    pool = new pg.Pool({ connectionString: url });
  }
  return pool;
}

export async function closePool() {
  if (pool) {
    await pool.end();
    pool = null;
  }
}

export async function pingDatabase() {
  const client = await getPool().connect();
  try {
    await client.query("SELECT 1");
  } finally {
    client.release();
  }
}
