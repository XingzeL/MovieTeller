import { getUserBalance, initUserBalance } from "../../db/balancesRepository.js";
import { getPlanByCode } from "../../db/plansRepository.js";
import {
  createSubscription,
  getActiveSubscription,
  upsertUser,
} from "../../db/usersRepository.js";

/**
 * Ensure users row, active free subscription, and balance exist.
 * @param {string} userId
 * @param {import('pg').PoolClient} [client]
 */
export async function upsertUserOnLogin(userId, client) {
  await upsertUser(userId, client);

  let subscription = await getActiveSubscription(userId, client);
  if (!subscription) {
    const freePlan = await getPlanByCode("free", client);
    if (!freePlan) {
      throw new Error("free plan is not seeded");
    }
    await createSubscription(userId, freePlan.id, client);
    subscription = await getActiveSubscription(userId, client);
  }

  const balance = await getUserBalance(userId, client);
  if (!balance && subscription) {
    const periodStart = new Date(subscription.period_start);
    const periodEnd = new Date(subscription.period_end);
    await initUserBalance(
      userId,
      {
        quotaMinutes: Number(subscription.quota_minutes_per_month),
        narrationQuotaMinutes: Number(subscription.narration_quota_minutes_per_month),
        periodStart,
        periodEnd,
      },
      client
    );
  }
}
