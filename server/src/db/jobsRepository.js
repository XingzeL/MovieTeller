import fs from "node:fs";

import { getPool } from "./pool.js";
import { jobRowToRecord } from "./jobRow.js";
import { readWorkflowRecord } from "../services/jobs/jobProcess.js";
import { jobPathsFromRoot } from "../config/jobs.js";
import { resolveCancelDeadlineAt } from "../services/jobs/cancelDeadline.js";

function utcNowIso() {
  return new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
}

/**
 * @param {import('pg').QueryResultRow} row
 */
export function rowToRecord(row) {
  return jobRowToRecord(row);
}

/**
 * @param {{
 *   jobId: string,
 *   userId: string,
 *   outputRoot: string,
 *   inputVideoPath: string,
 *   originalSource?: object | null,
 *   sourceDurationSec?: number | null,
 *   processedDurationSec?: number | null,
 *   quotaClipApplied?: boolean,
 *   quotaPolicy?: object | null,
 *   reservedMinutes?: number,
 *   reservedUsageDate?: string | null,
 * }} input
 * @param {import('pg').PoolClient} [client]
 */
export async function insertJobQueued(input, client) {
  const pool = client ?? getPool();
  await pool.query(
    `INSERT INTO jobs (
      job_id, user_id, status, attempt_id,
      output_root, input_video_path, original_source, video_state_version, progress,
      source_duration_sec, processed_duration_sec, quota_clip_applied,
      quota_policy, reserved_minutes, reserved_usage_date
    ) VALUES ($1, $2, 'queued', 1, $3, $4, $5::jsonb, 0, '{}'::jsonb,
      $6, $7, $8, $9::jsonb, $10, $11)`,
    [
      input.jobId,
      input.userId,
      input.outputRoot,
      input.inputVideoPath,
      input.originalSource ? JSON.stringify(input.originalSource) : null,
      input.sourceDurationSec ?? null,
      input.processedDurationSec ?? null,
      input.quotaClipApplied ?? false,
      input.quotaPolicy ? JSON.stringify(input.quotaPolicy) : null,
      input.reservedMinutes ?? 0,
      input.reservedUsageDate ?? null,
    ]
  );
}

/**
 * @param {string} jobId
 */
export async function getJobById(jobId) {
  const result = await getPool().query("SELECT * FROM jobs WHERE job_id = $1", [
    jobId,
  ]);
  if (result.rowCount === 0) return null;
  return rowToRecord(result.rows[0]);
}

/**
 * @param {string} userId
 * @param {{ limit?: number, offset?: number }} opts
 */
export async function listJobsForUserFromDb(userId, opts = {}) {
  const limit = Math.min(Math.max(1, opts.limit ?? 20), 1000);
  const offset = Math.max(0, opts.offset ?? 0);
  const countResult = await getPool().query(
    "SELECT COUNT(*)::int AS total FROM jobs WHERE user_id = $1",
    [userId]
  );
  const total = countResult.rows[0]?.total ?? 0;
  const result = await getPool().query(
    `SELECT * FROM jobs WHERE user_id = $1
     ORDER BY updated_at DESC
     LIMIT $2 OFFSET $3`,
    [userId, limit, offset]
  );
  return {
    rows: result.rows.map(rowToRecord),
    total,
    limit,
    offset,
  };
}

/**
 * @param {string} workerId
 */
export async function claimNextQueuedJob(workerId) {
  const result = await getPool().query(
    `UPDATE jobs SET
       status = 'running',
       claimed_at = now(),
       claimed_by = $1,
       last_heartbeat_at = now(),
       started_at = COALESCE(started_at, now()),
       updated_at = now()
     WHERE job_id = (
       SELECT job_id FROM jobs
       WHERE status = 'queued' AND cancel_requested_at IS NULL
       ORDER BY created_at
       FOR UPDATE SKIP LOCKED
       LIMIT 1
     )
     RETURNING *`,
    [workerId]
  );
  if (result.rowCount === 0) return null;
  return rowToRecord(result.rows[0]);
}

/**
 * @param {{ jobId: string, attemptId: number, claimedBy: string }} input
 */
export async function touchJobHeartbeat(input) {
  await getPool().query(
    `UPDATE jobs SET last_heartbeat_at = now(), updated_at = now()
     WHERE job_id = $1 AND attempt_id = $2 AND claimed_by = $3
       AND status IN ('running', 'canceling')`,
    [input.jobId, input.attemptId, input.claimedBy]
  );
}

/**
 * @param {{
 *   jobId: string,
 *   attemptId: number,
 *   claimedBy: string,
 *   patch: Record<string, unknown>,
 * }} input
 */
export async function updateJobConditional(input) {
  const sets = [];
  const values = [];
  let idx = 1;
  for (const [key, value] of Object.entries(input.patch)) {
    sets.push(`${key} = $${idx}`);
    values.push(value);
    idx += 1;
  }
  sets.push(`updated_at = now()`);
  values.push(input.jobId, input.attemptId, input.claimedBy);
  const sql = `UPDATE jobs SET ${sets.join(", ")}
    WHERE job_id = $${idx} AND attempt_id = $${idx + 1} AND claimed_by = $${idx + 2}`;
  const result = await getPool().query(sql, values);
  return result.rowCount > 0;
}

/**
 * Reconcile user-facing status from workflow.json after runner exits.
 * @param {string} jobRoot
 * @param {{ attemptId: number, claimedBy: string }} ctx
 */
export async function reconcileJobFromWorkflow(jobRoot, ctx) {
  const paths = jobPathsFromRoot(jobRoot);
  const workflow = readWorkflowRecord(paths.workflowJsonPath);
  if (!workflow?.job_id) return false;

  const status = String(workflow.status || "");
  const patch = {
    status,
    current_stage: workflow.current_stage ?? null,
    progress: workflow.progress ?? {},
    completed_at:
      ["succeeded", "failed", "canceled"].includes(status) ? utcNowIso() : null,
  };
  if (workflow.error && typeof workflow.error === "object") {
    patch.error_code = workflow.error.error_code ?? workflow.error.code ?? null;
    patch.error_message =
      workflow.error.error_message ?? workflow.error.message ?? null;
    patch.retryable = Boolean(workflow.error.retryable);
  } else if (status === "failed") {
    patch.retryable = true;
  } else if (status === "succeeded" || status === "canceled") {
    patch.error_code = null;
    patch.error_message = null;
    patch.retryable = false;
  }
  if (status === "canceled") {
    patch.canceled_at = workflow.canceled_at ?? utcNowIso();
    patch.cancel_mode = workflow.cancel_mode ?? "cooperative";
  }

  const entries = Object.entries(patch);
  const sets = entries.map(([key], i) => {
    if (key === "progress") return `progress = $${i + 1}::jsonb`;
    if (key === "completed_at") return `completed_at = $${i + 1}::timestamptz`;
    return `${key} = $${i + 1}`;
  });
  const values = entries.map(([key, value]) =>
    key === "progress" ? JSON.stringify(value) : value
  );
  values.push(workflow.job_id, ctx.attemptId, ctx.claimedBy);
  const sql = `UPDATE jobs SET ${sets.join(", ")}, updated_at = now()
    WHERE job_id = $${values.length - 2} AND attempt_id = $${values.length - 1}
      AND claimed_by = $${values.length}`;
  const result = await getPool().query(sql, values);
  return result.rowCount > 0;
}

/**
 * @param {string} userId
 * @param {string} jobId
 */
export async function markJobCanceling(userId, jobId) {
  const deadline = resolveCancelDeadlineAt();
  const result = await getPool().query(
    `UPDATE jobs SET
       status = 'canceling',
       cancel_requested_at = now(),
       cancel_deadline_at = $3,
       updated_at = now()
     WHERE job_id = $1 AND user_id = $2 AND status = 'running'
     RETURNING *`,
    [jobId, userId, deadline]
  );
  if (result.rowCount === 0) return null;
  return rowToRecord(result.rows[0]);
}

/**
 * @param {string} userId
 * @param {string} jobId
 */
export async function markJobCanceledQueued(userId, jobId) {
  const result = await getPool().query(
    `UPDATE jobs SET
       status = 'canceled',
       canceled_at = now(),
       cancel_mode = 'cooperative',
       completed_at = now(),
       updated_at = now()
     WHERE job_id = $1 AND user_id = $2 AND status = 'queued'
     RETURNING *`,
    [jobId, userId]
  );
  if (result.rowCount === 0) return null;
  return rowToRecord(result.rows[0]);
}

/**
 * @param {string} userId
 * @param {string} jobId
 */
export async function retryJobInDb(userId, jobId) {
  const inputPath = await getPool().query(
    "SELECT input_video_path, output_root FROM jobs WHERE job_id = $1 AND user_id = $2",
    [jobId, userId]
  );
  if (inputPath.rowCount === 0) {
    const err = new Error("job not found");
    err.statusCode = 404;
    throw err;
  }
  const { input_video_path: inputVideoPath } = inputPath.rows[0];
  if (!inputVideoPath || !fs.existsSync(inputVideoPath)) {
    const err = new Error("input video missing; cannot retry");
    err.statusCode = 400;
    throw err;
  }

  const result = await getPool().query(
    `UPDATE jobs SET
       status = 'queued',
       attempt_id = attempt_id + 1,
       error_code = NULL,
       error_message = NULL,
       retryable = false,
       claimed_at = NULL,
       claimed_by = NULL,
       last_heartbeat_at = NULL,
       started_at = NULL,
       completed_at = NULL,
       cancel_requested_at = NULL,
       cancel_acknowledged_at = NULL,
       cancel_deadline_at = NULL,
       canceled_at = NULL,
       cancel_mode = NULL,
       current_stage = NULL,
       progress = '{}'::jsonb,
       updated_at = now()
     WHERE job_id = $1 AND user_id = $2
       AND (
         status = 'canceled'
         OR (status = 'failed' AND retryable = true)
       )
     RETURNING *`,
    [jobId, userId]
  );
  if (result.rowCount === 0) {
    const err = new Error("cannot retry job in current status");
    err.statusCode = 409;
    throw err;
  }
  return rowToRecord(result.rows[0]);
}

/**
 * @param {{ staleSec?: number }} [opts]
 */
export async function sweepStaleJobs(opts = {}) {
  const staleSec = opts.staleSec ?? Number(process.env.STALE_HEARTBEAT_SEC || 90);
  const result = await getPool().query(
    `UPDATE jobs SET
       status = 'failed',
       error_code = 'stale_heartbeat',
       error_message = 'Worker heartbeat expired',
       retryable = true,
       completed_at = now(),
       updated_at = now()
     WHERE status IN ('running', 'canceling')
       AND last_heartbeat_at IS NOT NULL
       AND last_heartbeat_at < now() - ($1 || ' seconds')::interval
     RETURNING job_id`,
    [String(staleSec)]
  );
  return result.rows.map((r) => r.job_id);
}

/**
 * @param {string} jobId
 * @param {{ videoDownloadedAt?: string, videoPurgedAt?: string, videoStateVersion?: number }} patch
 */
export async function syncVideoStateToDb(jobId, patch) {
  const sets = [];
  const values = [];
  let i = 1;
  if (patch.videoDownloadedAt !== undefined) {
    sets.push(`video_downloaded_at = $${i++}::timestamptz`);
    values.push(patch.videoDownloadedAt);
  }
  if (patch.videoPurgedAt !== undefined) {
    sets.push(`video_purged_at = $${i++}::timestamptz`);
    values.push(patch.videoPurgedAt);
  }
  if (patch.videoStateVersion !== undefined) {
    sets.push(`video_state_version = $${i++}`);
    values.push(patch.videoStateVersion);
  }
  if (sets.length === 0) return;
  sets.push("updated_at = now()");
  values.push(jobId);
  await getPool().query(
    `UPDATE jobs SET ${sets.join(", ")} WHERE job_id = $${i}`,
    values
  );
}

/**
 * @param {string} jobId
 * @param {number} attemptId
 * @param {string} claimedBy
 */
export async function isJobCancelingForWorker(jobId, attemptId, claimedBy) {
  const result = await getPool().query(
    `SELECT 1 FROM jobs
     WHERE job_id = $1 AND attempt_id = $2 AND claimed_by = $3 AND status = 'canceling'
     LIMIT 1`,
    [jobId, attemptId, claimedBy]
  );
  return result.rowCount > 0;
}

export async function acknowledgeCancel(jobId, attemptId, claimedBy) {
  await getPool().query(
    `UPDATE jobs SET cancel_acknowledged_at = now(), updated_at = now()
     WHERE job_id = $1 AND attempt_id = $2 AND claimed_by = $3 AND status = 'canceling'`,
    [jobId, attemptId, claimedBy]
  );
}

/**
 * Mark a claimed job failed (worker prepare/spawn). Conditional on attempt + claimed_by.
 * @param {{
 *   jobId: string,
 *   attemptId: number,
 *   claimedBy: string,
 *   errorCode: string,
 *   errorMessage: string,
 *   retryable?: boolean,
 * }} input
 */
/**
 * @returns {Promise<import('./jobRow.js').JobRecord[]>}
 */
export async function listExpiredCancelingJobs() {
  const result = await getPool().query(
    `SELECT * FROM jobs
     WHERE status = 'canceling'
       AND cancel_deadline_at IS NOT NULL
       AND cancel_deadline_at < now()
     ORDER BY cancel_deadline_at`
  );
  return result.rows.map(rowToRecord);
}

/**
 * Eligibility only — does not change status (used before kill).
 * @param {{ jobId: string, attemptId: number, claimedBy: string }} input
 * @returns {Promise<boolean>}
 */
export async function isForcedCancelEligible(input) {
  const result = await getPool().query(
    `SELECT 1 FROM jobs
     WHERE job_id = $1 AND attempt_id = $2 AND claimed_by = $3
       AND status = 'canceling'
       AND cancel_deadline_at IS NOT NULL
       AND cancel_deadline_at < now()
     LIMIT 1`,
    [input.jobId, input.attemptId, input.claimedBy]
  );
  return result.rowCount > 0;
}

/**
 * Kill failed after deadline; keep canceling and record error for ops.
 * @param {{
 *   jobId: string,
 *   attemptId: number,
 *   claimedBy: string,
 *   detail: string,
 * }} input
 * @returns {Promise<boolean>}
 */
export async function recordForcedCancelKillFailed(input) {
  const result = await getPool().query(
    `UPDATE jobs SET
       error_code = 'forced_cancel_kill_failed',
       error_message = $4,
       updated_at = now()
     WHERE job_id = $1 AND attempt_id = $2 AND claimed_by = $3
       AND status = 'canceling'
       AND cancel_deadline_at IS NOT NULL
       AND cancel_deadline_at < now()
     RETURNING job_id`,
    [input.jobId, input.attemptId, input.claimedBy, input.detail]
  );
  return result.rowCount > 0;
}

/**
 * Finalize forced cancel after runner is gone (or was already gone).
 * @param {{ jobId: string, attemptId: number, claimedBy: string }} input
 * @returns {Promise<boolean>}
 */
export async function markJobForcedCanceledByWorker(input) {
  const result = await getPool().query(
    `UPDATE jobs SET
       status = 'canceled',
       cancel_mode = 'forced',
       canceled_at = now(),
       completed_at = now(),
       retryable = false,
       error_code = NULL,
       error_message = NULL,
       updated_at = now()
     WHERE job_id = $1 AND attempt_id = $2 AND claimed_by = $3
       AND status = 'canceling'
       AND cancel_deadline_at IS NOT NULL
       AND cancel_deadline_at < now()
     RETURNING job_id`,
    [input.jobId, input.attemptId, input.claimedBy]
  );
  return result.rowCount > 0;
}

export async function failJobByWorker(input) {
  const result = await getPool().query(
    `UPDATE jobs SET
       status = 'failed',
       error_code = $4,
       error_message = $5,
       retryable = $6,
       completed_at = now(),
       updated_at = now()
     WHERE job_id = $1 AND attempt_id = $2 AND claimed_by = $3
       AND status IN ('running', 'canceling')
     RETURNING job_id`,
    [
      input.jobId,
      input.attemptId,
      input.claimedBy,
      input.errorCode,
      input.errorMessage,
      input.retryable !== false,
    ]
  );
  return result.rowCount > 0;
}

/**
 * Terminal jobs older than retention window (Postgres control plane).
 * @param {number} maxAgeDays
 */
export async function listEligibleJobsForRetention(maxAgeDays) {
  const result = await getPool().query(
    `SELECT job_id, output_root, created_at
     FROM jobs
     WHERE status IN ('succeeded', 'failed', 'canceled')
       AND created_at < now() - ($1::int * interval '1 day')
     ORDER BY created_at`,
    [maxAgeDays]
  );
  return result.rows;
}

/**
 * @param {string} jobId
 * @returns {Promise<boolean>}
 */
export async function deleteJobById(jobId) {
  const result = await getPool().query("DELETE FROM jobs WHERE job_id = $1", [
    jobId,
  ]);
  return result.rowCount > 0;
}

/**
 * @param {string} jobId
 */
export async function jobExistsInDb(jobId) {
  const result = await getPool().query(
    "SELECT 1 FROM jobs WHERE job_id = $1 LIMIT 1",
    [jobId]
  );
  return result.rowCount > 0;
}

/**
 * @param {string} userId
 */
export async function countActiveJobsForUser(userId) {
  const result = await getPool().query(
    `SELECT COUNT(*)::int AS count FROM jobs
     WHERE user_id = $1 AND status IN ('queued', 'running', 'canceling')`,
    [userId]
  );
  return result.rows[0]?.count ?? 0;
}
