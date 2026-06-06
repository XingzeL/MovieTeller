import { isDbEnabled } from "../../db/database.js";
import { getPool } from "../../db/pool.js";

/**
 * @param {number} [maxAgeDays]
 * @returns {Promise<{ deleted: number, scanned: number }>}
 */
export async function purgeOldUsageLedger(maxAgeDays = 3) {
  if (!isDbEnabled()) {
    return { deleted: 0, scanned: 0 };
  }
  try {
    const countResult = await getPool().query(
      `SELECT COUNT(*)::int AS count FROM usage_ledger
       WHERE created_at < now() - ($1::int * interval '1 day')`,
      [maxAgeDays]
    );
    const scanned = countResult.rows[0]?.count ?? 0;
    const deleteResult = await getPool().query(
      `DELETE FROM usage_ledger
       WHERE created_at < now() - ($1::int * interval '1 day')`,
      [maxAgeDays]
    );
    return { deleted: deleteResult.rowCount ?? 0, scanned };
  } catch (err) {
    if (String(err?.message || "").includes("usage_ledger")) {
      return { deleted: 0, scanned: 0 };
    }
    throw err;
  }
}
