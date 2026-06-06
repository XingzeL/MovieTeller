import { getPool } from "./pool.js";

/**
 * @param {import('pg').PoolClient} [client]
 */
function queryClient(client) {
  return client ?? getPool();
}

/**
 * @returns {string} UTC date YYYY-MM-DD
 */
export function utcUsageDate() {
  return new Date().toISOString().slice(0, 10);
}

/**
 * @param {string} userId
 * @param {string} usageDate
 * @param {import('pg').PoolClient} client
 */
export async function ensureDailyUsageRow(userId, usageDate, client) {
  await client.query(
    `INSERT INTO user_daily_usage (user_id, usage_date, consumed_minutes, reserved_minutes)
     VALUES ($1, $2, 0, 0)
     ON CONFLICT (user_id, usage_date) DO NOTHING`,
    [userId, usageDate]
  );
}

/**
 * @param {string} userId
 * @param {string} usageDate
 * @param {import('pg').PoolClient} client
 */
export async function lockDailyUsage(userId, usageDate, client) {
  await ensureDailyUsageRow(userId, usageDate, client);
  const result = await client.query(
    `SELECT * FROM user_daily_usage
     WHERE user_id = $1 AND usage_date = $2
     FOR UPDATE`,
    [userId, usageDate]
  );
  return result.rows[0];
}

/**
 * @param {string} userId
 * @param {string} usageDate
 * @param {import('pg').PoolClient} [client]
 */
export async function getDailyUsage(userId, usageDate, client) {
  const result = await queryClient(client).query(
    "SELECT * FROM user_daily_usage WHERE user_id = $1 AND usage_date = $2",
    [userId, usageDate]
  );
  return result.rowCount > 0 ? result.rows[0] : null;
}

/**
 * @param {string} userId
 * @param {string} usageDate
 * @param {number} reservedDelta
 * @param {import('pg').PoolClient} client
 */
export async function adjustDailyReserved(userId, usageDate, reservedDelta, client) {
  await ensureDailyUsageRow(userId, usageDate, client);
  await client.query(
    `UPDATE user_daily_usage SET reserved_minutes = reserved_minutes + $3
     WHERE user_id = $1 AND usage_date = $2`,
    [userId, usageDate, reservedDelta]
  );
}

/**
 * @param {string} userId
 * @param {string} usageDate
 * @param {{ reservedDelta: number, consumedDelta: number }} deltas
 * @param {import('pg').PoolClient} client
 */
export async function applyDailyFinalize(userId, usageDate, deltas, client) {
  await ensureDailyUsageRow(userId, usageDate, client);
  await client.query(
    `UPDATE user_daily_usage SET
       reserved_minutes = GREATEST(0, reserved_minutes + $3),
       consumed_minutes = consumed_minutes + $4
     WHERE user_id = $1 AND usage_date = $2`,
    [userId, usageDate, deltas.reservedDelta, deltas.consumedDelta]
  );
}
