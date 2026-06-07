import {
  adjustNarrationReservedMinutes,
  adjustReservedMinutes,
} from "../../db/balancesRepository.js";
import { adjustDailyReserved, utcUsageDate } from "../../db/dailyUsageRepository.js";
import { getPool } from "../../db/pool.js";

/**
 * Release reserved minutes after create-time disk failure.
 * @param {string} userId
 * @param {number} reservedMinutes
 * @param {string} [usageDate]
 * @param {number} [reservedNarrationMinutes]
 */
export async function releaseQuota(
  userId,
  reservedMinutes,
  usageDate = utcUsageDate(),
  reservedNarrationMinutes = 0
) {
  if (
    (!reservedMinutes || reservedMinutes <= 0) &&
    (!reservedNarrationMinutes || reservedNarrationMinutes <= 0)
  ) return;

  const client = await getPool().connect();
  try {
    await client.query("BEGIN");
    if (reservedMinutes > 0) {
      await adjustReservedMinutes(userId, -reservedMinutes, client);
    }
    if (reservedNarrationMinutes > 0) {
      await adjustNarrationReservedMinutes(
        userId,
        -reservedNarrationMinutes,
        client
      );
    }
    await adjustDailyReserved(
      userId,
      usageDate,
      -reservedMinutes,
      client
    );
    await client.query("COMMIT");
  } catch (err) {
    await client.query("ROLLBACK");
    throw err;
  } finally {
    client.release();
  }
}
