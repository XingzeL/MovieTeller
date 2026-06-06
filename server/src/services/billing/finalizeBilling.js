import path from "node:path";

import { applyBillingFinalize, getUserBalance, lockUserBalance } from "../../db/balancesRepository.js";
import {
  applyDailyFinalize,
  lockDailyUsage,
  utcUsageDate,
} from "../../db/dailyUsageRepository.js";
import { getPool } from "../../db/pool.js";
import { insertUsageLedgerEntry } from "../../db/usageLedgerRepository.js";

/**
 * Idempotent terminal billing: release reservation and optionally consume quota.
 * @param {string} jobId
 */
export async function finalizeBilling(jobId) {
  const client = await getPool().connect();
  try {
    await client.query("BEGIN");

    const claimResult = await client.query(
      `UPDATE jobs SET billing_finalized_at = now(), updated_at = now()
       WHERE job_id = $1 AND billing_finalized_at IS NULL
       RETURNING *`,
      [jobId]
    );
    if (claimResult.rowCount === 0) {
      await client.query("COMMIT");
      return false;
    }

    const job = claimResult.rows[0];
    const userId = String(job.user_id);
    const status = String(job.status);
    const reservedMinutes = Number(job.reserved_minutes) || 0;
    const processedDurationSec = Number(job.processed_duration_sec) || 0;
    const sourceDurationSec = Number(job.source_duration_sec) || null;

    if (!["succeeded", "failed", "canceled"].includes(status)) {
      await client.query("ROLLBACK");
      return false;
    }

    const lockedBalance = await lockUserBalance(userId, client);
    if (!lockedBalance) {
      await client.query(
        `UPDATE jobs SET reserved_minutes = 0, updated_at = now() WHERE job_id = $1`,
        [jobId]
      );
      await client.query("COMMIT");
      return true;
    }

    const usageDate =
      job.reserved_usage_date instanceof Date
        ? job.reserved_usage_date.toISOString().slice(0, 10)
        : String(job.reserved_usage_date || utcUsageDate()).slice(0, 10);
    await lockDailyUsage(userId, usageDate, client);

    let consumedMinutes = 0;
    if (status === "succeeded" && reservedMinutes > 0) {
      consumedMinutes = reservedMinutes;
      await applyBillingFinalize(
        userId,
        { reservedDelta: -reservedMinutes, remainingDelta: -consumedMinutes },
        client
      );
      await applyDailyFinalize(
        userId,
        usageDate,
        { reservedDelta: -reservedMinutes, consumedDelta: consumedMinutes },
        client
      );
    } else if (reservedMinutes > 0) {
      await applyBillingFinalize(
        userId,
        { reservedDelta: -reservedMinutes, remainingDelta: 0 },
        client
      );
      await applyDailyFinalize(
        userId,
        usageDate,
        { reservedDelta: -reservedMinutes, consumedDelta: 0 },
        client
      );
    }

    await client.query(
      `UPDATE jobs SET reserved_minutes = 0, updated_at = now() WHERE job_id = $1`,
      [jobId]
    );

    const balance = await getUserBalance(userId, client);
    const remainingAfter = balance
      ? Math.max(0, Number(balance.remaining_minutes) - Number(balance.reserved_minutes))
      : 0;

    const originalSource =
      job.original_source && typeof job.original_source === "object"
        ? job.original_source
        : null;
    const videoName =
      originalSource?.original_filename ||
      (job.input_video_path
        ? path.basename(String(job.input_video_path))
        : null);

    await insertUsageLedgerEntry(
      {
        userId,
        jobId,
        videoName,
        sourceDurationSeconds: sourceDurationSec,
        processedDurationSeconds: processedDurationSec,
        consumedMinutes,
        remainingAfter,
        status,
      },
      client
    );

    await client.query("COMMIT");
    return true;
  } catch (err) {
    await client.query("ROLLBACK");
    throw err;
  } finally {
    client.release();
  }
}
