import { getUserBalance } from "../../db/balancesRepository.js";
import { sumConsumedInPeriod } from "../../db/usageLedgerRepository.js";
import { listUsageLedgerForUser } from "../../db/usageLedgerRepository.js";
import { ensureActiveBillingPeriod } from "./ensureActiveBillingPeriod.js";
import { upsertUserOnLogin } from "./upsertUserOnLogin.js";

/**
 * @param {string} userId
 * @param {{ limit?: number, offset?: number }} [opts]
 */
export async function getUsageForUser(userId, opts = {}) {
  await upsertUserOnLogin(userId);
  const balance = await ensureActiveBillingPeriod(userId);

  const periodStart = balance?.period_start
    ? new Date(balance.period_start)
    : new Date();
  const periodEnd = balance?.period_end ? new Date(balance.period_end) : null;

  const { consumedInPeriod, succeededCount } = await sumConsumedInPeriod(
    userId,
    periodStart
  );

  const remainingMinutes = balance
    ? Math.max(
        0,
        Number(balance.remaining_minutes) - Number(balance.reserved_minutes)
      )
    : 0;

  const ledger = await listUsageLedgerForUser(userId, {
    limit: opts.limit,
    offset: opts.offset,
    maxAgeDays: 3,
  });

  const records = ledger.rows.map((row) => ({
    id: String(row.id),
    jobId: row.job_id ? String(row.job_id) : row.job_id_snapshot,
    createdAt:
      row.created_at instanceof Date
        ? row.created_at.toISOString()
        : row.created_at,
    videoName: row.video_name ?? null,
    sourceDurationSeconds: row.source_duration_seconds ?? null,
    processedDurationSeconds: row.processed_duration_seconds ?? null,
    consumedMinutes: Number(row.consumed_minutes) || 0,
    remainingAfter: row.remaining_after ?? null,
    status: row.status,
  }));

  return {
    records,
    total: ledger.total,
    limit: ledger.limit,
    offset: ledger.offset,
    summary: {
      remainingMinutes,
      consumedInPeriod,
      succeededCount,
      periodStart: periodStart.toISOString(),
      periodEnd: periodEnd ? periodEnd.toISOString() : null,
      periodQuotaMinutes: balance ? Number(balance.period_quota_minutes) : null,
    },
  };
}
