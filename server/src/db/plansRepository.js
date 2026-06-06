import { getPool } from "./pool.js";

/**
 * @param {import('pg').PoolClient} [client]
 */
function queryClient(client) {
  return client ?? getPool();
}

/**
 * @param {string} planId
 * @param {import('pg').PoolClient} [client]
 */
export async function getPlanById(planId, client) {
  const result = await queryClient(client).query(
    "SELECT * FROM plans WHERE id = $1 AND is_active = true",
    [planId]
  );
  return result.rowCount > 0 ? result.rows[0] : null;
}

/**
 * @param {string} code
 * @param {import('pg').PoolClient} [client]
 */
export async function getPlanByCode(code, client) {
  const result = await queryClient(client).query(
    "SELECT * FROM plans WHERE code = $1 AND is_active = true",
    [code]
  );
  return result.rowCount > 0 ? result.rows[0] : null;
}
