import {
  getUserBalance,
  resetBalanceForNewPeriod,
} from "../../db/balancesRepository.js";
import { countActiveJobsForUser } from "../../db/jobsRepository.js";
import { getActiveSubscription } from "../../db/usersRepository.js";

/**
 * Lazy-refresh billing period when expired and no active jobs.
 * @param {string} userId
 * @param {import('pg').PoolClient} [client]
 */
export async function ensureActiveBillingPeriod(userId, client) {
  const balance = await getUserBalance(userId, client);
  if (!balance) {
    return null;
  }

  const periodEnd = new Date(balance.period_end);
  if (periodEnd > new Date()) {
    return balance;
  }

  const activeJobs = await countActiveJobsForUser(userId);
  if (activeJobs > 0) {
    return balance;
  }

  const subscription = await getActiveSubscription(userId, client);
  if (!subscription) {
    return balance;
  }

  const now = new Date();
  const nextEnd = new Date(now);
  nextEnd.setUTCDate(nextEnd.getUTCDate() + 30);

  await resetBalanceForNewPeriod(
    userId,
    {
      quotaMinutes: Number(subscription.quota_minutes_per_month),
      narrationQuotaMinutes: Number(subscription.narration_quota_minutes_per_month),
      periodStart: now,
      periodEnd: nextEnd,
    },
    /** @type {import('pg').PoolClient} */ (client)
  );

  return getUserBalance(userId, client);
}
