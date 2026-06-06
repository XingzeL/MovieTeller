import { getPool } from "./pool.js";

/**
 * @param {{
 *   userId: string,
 *   jobId: string,
 *   videoName?: string | null,
 *   sourceDurationSeconds?: number | null,
 *   processedDurationSeconds?: number | null,
 *   consumedMinutes: number,
 *   remainingAfter: number,
 *   status: string,
 * }} input
 * @param {import('pg').PoolClient} client
 */
export async function insertUsageLedgerEntry(input, client) {
  await client.query(
    `INSERT INTO usage_ledger (
       user_id, job_id, job_id_snapshot, video_name,
       source_duration_seconds, processed_duration_seconds,
       consumed_minutes, remaining_after, status
     ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)`,
    [
      input.userId,
      input.jobId,
      input.jobId,
      input.videoName ?? null,
      input.sourceDurationSeconds ?? null,
      input.processedDurationSeconds ?? null,
      input.consumedMinutes,
      input.remainingAfter,
      input.status,
    ]
  );
}

/**
 * @param {string} userId
 * @param {{ limit?: number, offset?: number, maxAgeDays?: number }} [opts]
 */
export async function listUsageLedgerForUser(userId, opts = {}) {
  const limit = Math.min(Math.max(1, opts.limit ?? 50), 200);
  const offset = Math.max(0, opts.offset ?? 0);
  const maxAgeDays = opts.maxAgeDays ?? 3;

  const result = await getPool().query(
    `SELECT * FROM usage_ledger
     WHERE user_id = $1
       AND created_at >= now() - ($4::int * interval '1 day')
     ORDER BY created_at DESC
     LIMIT $2 OFFSET $3`,
    [userId, limit, offset, maxAgeDays]
  );

  const countResult = await getPool().query(
    `SELECT COUNT(*)::int AS total FROM usage_ledger
     WHERE user_id = $1
       AND created_at >= now() - ($2::int * interval '1 day')`,
    [userId, maxAgeDays]
  );

  return {
    rows: result.rows,
    total: countResult.rows[0]?.total ?? 0,
    limit,
    offset,
  };
}

/**
 * @param {string} userId
 * @param {Date} periodStart
 */
export async function sumConsumedInPeriod(userId, periodStart) {
  const result = await getPool().query(
    `SELECT COALESCE(SUM(consumed_minutes), 0)::int AS total,
            COUNT(*) FILTER (WHERE status = 'succeeded')::int AS succeeded_count
     FROM usage_ledger
     WHERE user_id = $1 AND created_at >= $2`,
    [userId, periodStart.toISOString()]
  );
  return {
    consumedInPeriod: result.rows[0]?.total ?? 0,
    succeededCount: result.rows[0]?.succeeded_count ?? 0,
  };
}
