import { getPool } from "./pool.js";

/**
 * @param {import('pg').PoolClient} [client]
 */
function queryClient(client) {
  return client ?? getPool();
}

/**
 * @param {string} userId
 * @param {import('pg').PoolClient} [client]
 */
export async function upsertUser(userId, client) {
  await queryClient(client).query(
    `INSERT INTO users (id) VALUES ($1)
     ON CONFLICT (id) DO UPDATE SET updated_at = now()`,
    [userId]
  );
}

/**
 * @param {string} userId
 * @param {import('pg').PoolClient} [client]
 */
export async function getActiveSubscription(userId, client) {
  const result = await queryClient(client).query(
    `SELECT us.*, p.code AS plan_code, p.quota_minutes_per_month,
            p.narration_quota_minutes_per_month,
            p.max_video_duration_sec, p.max_daily_minutes
     FROM user_subscriptions us
     JOIN plans p ON p.id = us.plan_id
     WHERE us.user_id = $1 AND us.status = 'active'
     ORDER BY us.created_at DESC
     LIMIT 1`,
    [userId]
  );
  return result.rowCount > 0 ? result.rows[0] : null;
}

/**
 * @param {string} userId
 * @param {string} planId
 * @param {import('pg').PoolClient} [client]
 */
/**
 * @param {string} userId
 * @param {string} planId
 * @param {import('pg').PoolClient} [client]
 */
export async function switchActiveSubscription(userId, planId, client) {
  await queryClient(client).query(
    `UPDATE user_subscriptions SET status = 'canceled'
     WHERE user_id = $1 AND status = 'active'`,
    [userId]
  );
  return createSubscription(userId, planId, client);
}

export async function createSubscription(userId, planId, client) {
  const now = new Date();
  const periodEnd = new Date(now);
  periodEnd.setUTCDate(periodEnd.getUTCDate() + 30);
  const result = await queryClient(client).query(
    `INSERT INTO user_subscriptions (user_id, plan_id, status, period_start, period_end)
     VALUES ($1, $2, 'active', $3, $4)
     RETURNING *`,
    [userId, planId, now.toISOString(), periodEnd.toISOString()]
  );
  return result.rows[0];
}
