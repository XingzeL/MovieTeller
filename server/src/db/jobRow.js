/**
 * Map Postgres jobs row to workflow.json-shaped record for DTO builders.
 * @param {Record<string, unknown>} row
 */
export function jobRowToRecord(row) {
  return {
    job_id: String(row.job_id),
    user_id: row.user_id,
    status: row.status,
    attempt_id: row.attempt_id,
    input_video_path: row.input_video_path,
    output_root: row.output_root,
    current_stage: row.current_stage ?? null,
    progress:
      row.progress && typeof row.progress === "object" ? row.progress : {},
    error:
      row.error_code || row.error_message
        ? {
            error_code: row.error_code ?? undefined,
            error_message: row.error_message ?? undefined,
            retryable: row.retryable ?? false,
          }
        : null,
    artifacts: {},
    created_at:
      row.created_at instanceof Date
        ? row.created_at.toISOString().replace(/\.\d{3}Z$/, "Z")
        : row.created_at,
    updated_at:
      row.updated_at instanceof Date
        ? row.updated_at.toISOString().replace(/\.\d{3}Z$/, "Z")
        : row.updated_at,
    started_at: row.started_at
      ? row.started_at instanceof Date
        ? row.started_at.toISOString().replace(/\.\d{3}Z$/, "Z")
        : row.started_at
      : null,
    completed_at: row.completed_at
      ? row.completed_at instanceof Date
        ? row.completed_at.toISOString().replace(/\.\d{3}Z$/, "Z")
        : row.completed_at
      : null,
    cancel_requested_at: row.cancel_requested_at
      ? row.cancel_requested_at instanceof Date
        ? row.cancel_requested_at.toISOString().replace(/\.\d{3}Z$/, "Z")
        : row.cancel_requested_at
      : null,
    cancel_acknowledged_at: row.cancel_acknowledged_at ?? null,
    cancel_deadline_at: row.cancel_deadline_at ?? null,
    canceled_at: row.canceled_at ?? null,
    cancel_mode: row.cancel_mode ?? null,
    original_source: row.original_source ?? null,
    video_downloaded_at: row.video_downloaded_at
      ? row.video_downloaded_at instanceof Date
        ? row.video_downloaded_at.toISOString().replace(/\.\d{3}Z$/, "Z")
        : row.video_downloaded_at
      : null,
    video_purged_at: row.video_purged_at
      ? row.video_purged_at instanceof Date
        ? row.video_purged_at.toISOString().replace(/\.\d{3}Z$/, "Z")
        : row.video_purged_at
      : null,
    video_state_version: row.video_state_version ?? 0,
    claimed_by: row.claimed_by ?? null,
  };
}
