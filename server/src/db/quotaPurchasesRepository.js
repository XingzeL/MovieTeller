import { getPool } from "./pool.js";

/**
 * @param {import('pg').PoolClient} [client]
 */
function queryClient(client) {
  return client ?? getPool();
}

/**
 * @param {{
 *   userId: string,
 *   kind: string,
 *   productId: string,
 *   processingMinutes: number,
 *   narrationMinutes: number,
 *   maxVideoDurationSec?: number | null,
 * }} input
 * @param {import('pg').PoolClient} [client]
 */
export async function insertQuotaPurchase(input, client) {
  await queryClient(client).query(
    `INSERT INTO quota_purchases (
       user_id, kind, product_id,
       processing_minutes, narration_minutes, max_video_duration_sec
     ) VALUES ($1, $2, $3, $4, $5, $6)`,
    [
      input.userId,
      input.kind,
      input.productId,
      input.processingMinutes,
      input.narrationMinutes,
      input.maxVideoDurationSec ?? null,
    ]
  );
}
