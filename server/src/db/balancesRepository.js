import { getPool } from "./pool.js";

/**
 * @param {import('pg').PoolClient} [client]
 */
function queryClient(client) {
  return client ?? getPool();
}

/**
 * @param {Record<string, unknown>} balance
 */
export function getProcessingAvailableMinutes(balance) {
  const period = Math.max(
    0,
    Number(balance.remaining_minutes) - Number(balance.reserved_minutes)
  );
  const bonus = Math.max(0, Number(balance.bonus_processing_minutes) || 0);
  return period + bonus;
}

/**
 * @param {Record<string, unknown>} balance
 */
export function getNarrationAvailableMinutes(balance) {
  const period = Math.max(
    0,
    Number(balance.narration_remaining_minutes) -
      Number(balance.narration_reserved_minutes)
  );
  const bonus = Math.max(0, Number(balance.bonus_narration_minutes) || 0);
  return period + bonus;
}

/**
 * @param {{ max_video_duration_sec?: number }} plan
 * @param {Record<string, unknown>} balance
 */
export function getEffectiveMaxVideoDurationSec(plan, balance) {
  const planMax = Number(plan.max_video_duration_sec) || 0;
  const override = Number(balance.max_video_duration_sec_override) || 0;
  return Math.max(planMax, override);
}

/**
 * @param {string} userId
 * @param {{ quotaMinutes: number, narrationQuotaMinutes?: number, periodStart: Date, periodEnd: Date }} input
 * @param {import('pg').PoolClient} [client]
 */
export async function initUserBalance(userId, input, client) {
  await queryClient(client).query(
    `INSERT INTO user_balances (
       user_id, remaining_minutes, reserved_minutes,
       narration_remaining_minutes, narration_reserved_minutes,
       period_quota_minutes, narration_period_quota_minutes,
       period_start, period_end
     ) VALUES ($1, $2, 0, $3, 0, $2, $3, $4, $5)
     ON CONFLICT (user_id) DO NOTHING`,
    [
      userId,
      input.quotaMinutes,
      input.narrationQuotaMinutes ?? input.quotaMinutes,
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
 * @param {{ quotaMinutes: number, narrationQuotaMinutes?: number, periodStart: Date, periodEnd: Date }} input
 * @param {import('pg').PoolClient} client
 */
export async function resetBalanceForNewPeriod(userId, input, client) {
  await queryClient(client).query(
    `UPDATE user_balances SET
       remaining_minutes = $2 + bonus_processing_minutes,
       reserved_minutes = 0,
       narration_remaining_minutes = $3 + bonus_narration_minutes,
       narration_reserved_minutes = 0,
       period_quota_minutes = $2,
       narration_period_quota_minutes = $3,
       period_start = $4,
       period_end = $5,
       updated_at = now()
     WHERE user_id = $1`,
    [
      userId,
      input.quotaMinutes,
      input.narrationQuotaMinutes ?? input.quotaMinutes,
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
 * @param {number} delta
 * @param {import('pg').PoolClient} client
 */
export async function adjustNarrationReservedMinutes(userId, delta, client) {
  await client.query(
    `UPDATE user_balances SET
       narration_reserved_minutes = narration_reserved_minutes + $2,
       updated_at = now()
     WHERE user_id = $1`,
    [userId, delta]
  );
}

/**
 * @param {string} userId
 * @param {{
 *   processingMinutes: number,
 *   narrationMinutes: number,
 *   maxVideoDurationSec?: number | null,
 * }} input
 * @param {import('pg').PoolClient} [client]
 */
export async function addPurchasedQuota(userId, input, client) {
  const processing = Math.max(0, Number(input.processingMinutes) || 0);
  const narration = Math.max(0, Number(input.narrationMinutes) || 0);
  if (processing === 0 && narration === 0 && input.maxVideoDurationSec == null) {
    return;
  }

  await queryClient(client).query(
    `UPDATE user_balances SET
       remaining_minutes = remaining_minutes + $2,
       narration_remaining_minutes = narration_remaining_minutes + $3,
       bonus_processing_minutes = bonus_processing_minutes + $2,
       bonus_narration_minutes = bonus_narration_minutes + $3,
       max_video_duration_sec_override = CASE
         WHEN $4::int IS NULL THEN max_video_duration_sec_override
         ELSE GREATEST(COALESCE(max_video_duration_sec_override, 0), $4::int)
       END,
       updated_at = now()
     WHERE user_id = $1`,
    [
      userId,
      processing,
      narration,
      input.maxVideoDurationSec ?? null,
    ]
  );
}

/**
 * @deprecated Use addPurchasedQuota for mock purchases.
 * @param {string} userId
 * @param {{ processingMinutes: number, narrationMinutes: number }} input
 * @param {import('pg').PoolClient} [client]
 */
export async function addRemainingQuota(userId, input, client) {
  await addPurchasedQuota(userId, input, client);
}

/**
 * @param {string} userId
 * @param {{ processingMinutes: number, narrationMinutes: number }} amounts
 * @param {import('pg').PoolClient} client
 */
export async function applyQuotaConsumption(userId, amounts, client) {
  const balance = await lockUserBalance(userId, client);
  if (!balance) return;

  let processingLeft = Math.max(0, Number(amounts.processingMinutes) || 0);
  let narrationLeft = Math.max(0, Number(amounts.narrationMinutes) || 0);

  let remainingMinutes = Number(balance.remaining_minutes) || 0;
  let bonusProcessing = Number(balance.bonus_processing_minutes) || 0;
  let narrationRemaining = Number(balance.narration_remaining_minutes) || 0;
  let bonusNarration = Number(balance.bonus_narration_minutes) || 0;

  const fromPeriodProcessing = Math.min(remainingMinutes, processingLeft);
  remainingMinutes -= fromPeriodProcessing;
  processingLeft -= fromPeriodProcessing;
  bonusProcessing = Math.max(0, bonusProcessing - processingLeft);

  const fromPeriodNarration = Math.min(narrationRemaining, narrationLeft);
  narrationRemaining -= fromPeriodNarration;
  narrationLeft -= fromPeriodNarration;
  bonusNarration = Math.max(0, bonusNarration - narrationLeft);

  await client.query(
    `UPDATE user_balances SET
       remaining_minutes = $2,
       bonus_processing_minutes = $3,
       narration_remaining_minutes = $4,
       bonus_narration_minutes = $5,
       updated_at = now()
     WHERE user_id = $1`,
    [
      userId,
      remainingMinutes,
      bonusProcessing,
      narrationRemaining,
      bonusNarration,
    ]
  );
}

/**
 * @param {string} userId
 * @param {{ reservedDelta: number, remainingDelta: number, narrationReservedDelta?: number, narrationRemainingDelta?: number }} deltas
 * @param {import('pg').PoolClient} client
 */
export async function applyBillingFinalize(userId, deltas, client) {
  await client.query(
    `UPDATE user_balances SET
       reserved_minutes = GREATEST(0, reserved_minutes + $2),
       remaining_minutes = GREATEST(0, remaining_minutes + $3),
       narration_reserved_minutes = GREATEST(0, narration_reserved_minutes + $4),
       narration_remaining_minutes = GREATEST(0, narration_remaining_minutes + $5),
       updated_at = now()
     WHERE user_id = $1`,
    [
      userId,
      deltas.reservedDelta,
      deltas.remainingDelta,
      deltas.narrationReservedDelta ?? 0,
      deltas.narrationRemainingDelta ?? 0,
    ]
  );
}
