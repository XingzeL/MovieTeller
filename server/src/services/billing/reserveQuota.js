import { adjustReservedMinutes, lockUserBalance } from "../../db/balancesRepository.js";
import {
  adjustDailyReserved,
  lockDailyUsage,
  utcUsageDate,
} from "../../db/dailyUsageRepository.js";
import { insertJobQueued } from "../../db/jobsRepository.js";
import { getPool } from "../../db/pool.js";
import { getActiveSubscription } from "../../db/usersRepository.js";
import { PlanQuotaExhaustedError } from "./errors.js";
import { ensureActiveBillingPeriod } from "./ensureActiveBillingPeriod.js";
import { resolveProcessingRange } from "./resolveProcessingRange.js";
import { upsertUserOnLogin } from "./upsertUserOnLogin.js";

/**
 * Reserve quota and insert queued job in one transaction.
 * @param {{
 *   userId: string,
 *   jobId: string,
 *   outputRoot: string,
 *   inputVideoPath: string,
 *   originalSource?: object | null,
 *   sourceDurationSec: number,
 * }} input
 */
export async function reserveQuotaAndInsertJob(input) {
  const client = await getPool().connect();
  try {
    await client.query("BEGIN");
    await upsertUserOnLogin(input.userId, client);
    await ensureActiveBillingPeriod(input.userId, client);

    const subscription = await getActiveSubscription(input.userId, client);
    if (!subscription) {
      throw new Error("no active subscription");
    }

    const balance = await lockUserBalance(input.userId, client);
    if (!balance) {
      throw new Error("user balance missing");
    }

    const usageDate = utcUsageDate();
    const dailyUsage = await lockDailyUsage(
      input.userId,
      usageDate,
      client
    );

    const range = resolveProcessingRange({
      sourceDurationSec: input.sourceDurationSec,
      plan: subscription,
      balance,
      dailyUsage,
    });

    if (range.needMinutes < 1) {
      throw new PlanQuotaExhaustedError();
    }

    const monthlyAvailable =
      Number(balance.remaining_minutes) - Number(balance.reserved_minutes);
    if (monthlyAvailable < range.needMinutes) {
      throw new PlanQuotaExhaustedError();
    }

    if (subscription.max_daily_minutes != null) {
      const dailyAvailable =
        Number(subscription.max_daily_minutes) -
        Number(dailyUsage.consumed_minutes) -
        Number(dailyUsage.reserved_minutes);
      if (dailyAvailable < range.needMinutes) {
        throw new PlanQuotaExhaustedError();
      }
    }

    await adjustReservedMinutes(input.userId, range.needMinutes, client);
    await adjustDailyReserved(
      input.userId,
      usageDate,
      range.needMinutes,
      client
    );

    await insertJobQueued(
      {
        jobId: input.jobId,
        userId: input.userId,
        outputRoot: input.outputRoot,
        inputVideoPath: input.inputVideoPath,
        originalSource: input.originalSource,
        sourceDurationSec: input.sourceDurationSec,
        processedDurationSec: range.processedDurationSec,
        quotaClipApplied: range.quotaClipApplied,
        quotaPolicy: range.quotaPolicy,
        reservedMinutes: range.needMinutes,
        reservedUsageDate: usageDate,
      },
      client
    );

    await client.query("COMMIT");
    return { ...range, reservedUsageDate: usageDate };
  } catch (err) {
    await client.query("ROLLBACK");
    throw err;
  } finally {
    client.release();
  }
}
