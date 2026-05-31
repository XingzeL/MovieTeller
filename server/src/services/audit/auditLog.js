import fs from "node:fs";
import path from "node:path";

import { getJobsRoot, jobPathsFromRoot, resolveJobRoot } from "../../config/jobs.js";

const SCHEMA_VERSION = 1;

/**
 * Append an audit event to per-job logs/audit.jsonl (best-effort).
 * @param {{ jobId: string, userId: string, event: string, detail?: Record<string, unknown> }} entry
 */
export function appendAuditEvent(entry) {
  try {
    const jobRoot = resolveJobRoot(getJobsRoot(), entry.jobId);
    const paths = jobPathsFromRoot(jobRoot);
    fs.mkdirSync(paths.logsDir, { recursive: true });
    const line = {
      schema_version: SCHEMA_VERSION,
      ts: new Date().toISOString(),
      user_id: entry.userId,
      job_id: entry.jobId,
      event: entry.event,
      ...(entry.detail ? { detail: entry.detail } : {}),
    };
    fs.appendFileSync(
      path.join(paths.logsDir, "audit.jsonl"),
      `${JSON.stringify(line)}\n`,
      "utf8"
    );
  } catch (err) {
    console.error("[Audit] append failed", entry.event, err);
  }
}
