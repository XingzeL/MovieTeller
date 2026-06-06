import { getPool } from "./pool.js";

/**
 * @param {import('pg').PoolClient} [client]
 */
function queryClient(client) {
  return client ?? getPool();
}

/**
 * @param {string} userId
 * @param {{ quotaMinutes: number, periodStart: Date, periodEnd: Date }} input
 * @param {import('pg').PoolClient} [client]
 */
export async function initUserBalance(userId, input, client) {
  await queryClient(client).query(
    `INSERT INTO user_balances (
       user_id, remaining_minutes, reserved_minutes,
       period_quota_minutes, period_start, period_end
     ) VALUES ($1, $2, 0, $2, $3, $4)
     ON CONFLICT (user_id) DO NOTHING`,
    [
      userId,
      input.quotaMinutes,
      input.periodStart.toISOString(),
      input.periodEnd.toISOString(),
    ]
  );
}

/**
 * @param {string} userId
 * @param {import('pg').PoolClient} [client]
 */
export async function getUserBalance(userId, client) {
  const result = await queryClient(client).query(
    "SELECT * FROM user_balances WHERE user_id = $1",
    [userId]
  );
  return result.rowCount > 0 ? result.rows[0] : null;
}

/**
 * @param {string} userId
 * @param {import('pg').PoolClient} client
 */
export async function lockUserBalance(userId, client) {
  const result = await client.query(
    "SELECT * FROM user_balances WHERE user_id = $1 FOR UPDATE",
    [userId]
  );
  return result.rowCount > 0 ? result.rows[0] : null;
}

/**
 * @param {string} userId
 * @param {{ quotaMinutes: number, periodStart: Date, periodEnd: Date }} input
 * @param {import('pg').PoolClient} client
 */
export async function resetBalanceForNewPeriod(userId, input, client) {
  await queryClient(client).query(
    `UPDATE user_balances SET
       remaining_minutes = $2,
       reserved_minutes = 0,
       period_quota_minutes = $2,
       period_start = $3,
       period_end = $4,
       updated_at = now()
     WHERE user_id = $1`,
    [
      userId,
      input.quotaMinutes,
      input.periodStart.toISOString(),
      input.periodEnd.toISOString(),
    ]
  );
}

/**
 * @param {string} userId
 * @param {number} delta
 * @param {import('pg').PoolClient} client
 */
export async function adjustReservedMinutes(userId, delta, client) {
  await client.query(
    `UPDATE user_balances SET
       reserved_minutes = reserved_minutes + $2,
       updated_at = now()
     WHERE user_id = $1`,
    [userId, delta]
  );
}

/**
 * @param {string} userId
 * @param {{ reservedDelta: number, remainingDelta: number }} deltas
 * @param {import('pg').PoolClient} client
 */
export async function applyBillingFinalize(userId, deltas, client) {
  await client.query(
    `UPDATE user_balances SET
       reserved_minutes = GREATEST(0, reserved_minutes + $2),
       remaining_minutes = GREATEST(0, remaining_minutes + $3),
       updated_at = now()
     WHERE user_id = $1`,
    [userId, deltas.reservedDelta, deltas.remainingDelta]
  );
}
