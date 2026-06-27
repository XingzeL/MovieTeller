import {
  getNarrationAvailableMinutes,
  getProcessingAvailableMinutes,
  lockUserBalance,
} from "../../db/balancesRepository.js";
import { lockDailyUsage, utcUsageDate } from "../../db/dailyUsageRepository.js";
import { getPool } from "../../db/pool.js";
import { getActiveSubscription } from "../../db/usersRepository.js";
import { PlanQuotaExhaustedError } from "./errors.js";
import { ensureActiveBillingPeriod } from "./ensureActiveBillingPeriod.js";
import { resolveProcessingRange } from "./resolveProcessingRange.js";
import { upsertUserOnLogin } from "./upsertUserOnLogin.js";

/**
 * Read-only quota check before remote download. Throws PlanQuotaExhaustedError when blocked.
 * @param {{ userId: string, sourceDurationSec: number, enableSpeech?: boolean }} input
 */
export async function preflightQuotaForDuration(input) {
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
    const dailyUsage = await lockDailyUsage(input.userId, usageDate, client);
    const enableSpeech = input.enableSpeech !== false;

    const range = resolveProcessingRange({
      sourceDurationSec: input.sourceDurationSec,
      enableSpeech,
      plan: subscription,
      balance,
      dailyUsage,
    });

    if (range.needMinutes < 1) {
      const processingAvailable =
        Number(range.quotaPolicy?.processingAvailableMinutes) || 0;
      const narrationAvailable =
        range.enableSpeech && range.quotaPolicy?.narrationAvailableMinutes != null
          ? Number(range.quotaPolicy.narrationAvailableMinutes) || 0
          : Number.POSITIVE_INFINITY;
      const dailyAvailable =
        range.quotaPolicy?.dailyAvailableMinutes != null
          ? Number(range.quotaPolicy.dailyAvailableMinutes) || 0
          : Number.POSITIVE_INFINITY;
      let reason = "processing_quota_exhausted";
      let message = "processing quota exhausted";
      if (processingAvailable >= 1 && narrationAvailable < 1) {
        reason = "narration_quota_exhausted";
        message = "narration quota exhausted";
      } else if (processingAvailable >= 1 && dailyAvailable < 1) {
        reason = "daily_processing_quota_exhausted";
        message = "daily processing quota exhausted";
      }
      throw new PlanQuotaExhaustedError(message, reason);
    }

    const monthlyAvailable = getProcessingAvailableMinutes(balance);
    if (monthlyAvailable < range.needMinutes) {
      throw new PlanQuotaExhaustedError(
        "processing quota exhausted",
        "processing_quota_exhausted"
      );
    }
    if (range.needNarrationMinutes > 0) {
      const narrationAvailable = getNarrationAvailableMinutes(balance);
      if (narrationAvailable < range.needNarrationMinutes) {
        throw new PlanQuotaExhaustedError(
          "narration quota exhausted",
          "narration_quota_exhausted"
        );
      }
    }

    if (subscription.max_daily_minutes != null) {
      const dailyAvailable =
        Number(subscription.max_daily_minutes) -
        Number(dailyUsage.consumed_minutes) -
        Number(dailyUsage.reserved_minutes);
      if (dailyAvailable < range.needMinutes) {
        throw new PlanQuotaExhaustedError(
          "daily processing quota exhausted",
          "daily_processing_quota_exhausted"
        );
      }
    }

    await client.query("COMMIT");
    return range;
  } catch (err) {
    await client.query("ROLLBACK");
    throw err;
  } finally {
    client.release();
  }
}
