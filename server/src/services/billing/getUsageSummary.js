import {
  getNarrationAvailableMinutes,
  getProcessingAvailableMinutes,
  getUserBalance,
} from "../../db/balancesRepository.js";
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

  const {
    consumedInPeriod,
    processingConsumedInPeriod,
    narrationConsumedInPeriod,
    succeededCount,
  } = await sumConsumedInPeriod(userId, periodStart);

  const remainingMinutes = balance ? getProcessingAvailableMinutes(balance) : 0;
  const narrationRemainingMinutes = balance
    ? getNarrationAvailableMinutes(balance)
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
    processingConsumedMinutes:
      Number(row.processing_consumed_minutes ?? row.consumed_minutes) || 0,
    narrationConsumedMinutes: Number(row.narration_consumed_minutes) || 0,
    remainingAfter: row.remaining_after ?? null,
    narrationRemainingAfter: row.narration_remaining_after ?? null,
    status: row.status,
  }));

  return {
    records,
    total: ledger.total,
    limit: ledger.limit,
    offset: ledger.offset,
    summary: {
      remainingMinutes,
      processingRemainingMinutes: remainingMinutes,
      narrationRemainingMinutes,
      consumedInPeriod,
      processingConsumedInPeriod,
      narrationConsumedInPeriod,
      succeededCount,
      periodStart: periodStart.toISOString(),
      periodEnd: periodEnd ? periodEnd.toISOString() : null,
      periodQuotaMinutes: balance ? Number(balance.period_quota_minutes) : null,
      narrationPeriodQuotaMinutes: balance
        ? Number(balance.narration_period_quota_minutes)
        : null,
    },
  };
}
