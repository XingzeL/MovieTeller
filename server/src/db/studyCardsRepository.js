import { getPool } from "./pool.js";

/**
 * @param {{ jobId: string, html: string, sourcePath?: string | null }} input
 */
export async function upsertStudyCards(input) {
  const byteSize = Buffer.byteLength(input.html, "utf8");
  await getPool().query(
    `INSERT INTO job_study_cards (job_id, html, byte_size, source_path)
     VALUES ($1, $2, $3, $4)
     ON CONFLICT (job_id) DO UPDATE SET
       html = EXCLUDED.html,
       byte_size = EXCLUDED.byte_size,
       source_path = EXCLUDED.source_path,
       stored_at = now()`,
    [input.jobId, input.html, byteSize, input.sourcePath ?? null]
  );
}

/**
 * @param {string} jobId
 */
export async function getStudyCardsByJobId(jobId) {
  const result = await getPool().query(
    "SELECT * FROM job_study_cards WHERE job_id = $1",
    [jobId]
  );
  return result.rowCount > 0 ? result.rows[0] : null;
}
