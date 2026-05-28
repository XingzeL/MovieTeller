import fs from "node:fs";
import path from "node:path";

import { isTerminalJobStatus, jobPathsFromRoot } from "../../config/jobs.js";

/**
 * @param {string} workflowJsonPath
 * @returns {Record<string, unknown> | null}
 */
export function readWorkflowRecord(workflowJsonPath) {
  if (!fs.existsSync(workflowJsonPath)) {
    return null;
  }
  try {
    const record = JSON.parse(fs.readFileSync(workflowJsonPath, "utf8"));
    return record && typeof record === "object" ? record : null;
  } catch {
    return null;
  }
}

/**
 * @param {string} jobRoot
 * @param {{ error_code?: string, message?: string, exitCode?: number | null }} error
 */
export function markJobFailed(jobRoot, error) {
  const paths = jobPathsFromRoot(jobRoot);
  const record = readWorkflowRecord(paths.workflowJsonPath);
  if (record && isTerminalJobStatus(record.status)) {
    return false;
  }
  const now = new Date().toISOString();
  const next = {
    ...(record || {}),
    job_id: record?.job_id || path.basename(jobRoot),
    status: "failed",
    output_root: record?.output_root || paths.root,
    error: {
      error_code: error.error_code || "runner_failed",
      error_message: error.message || "workflow runner failed",
      exit_code: error.exitCode ?? null,
      retryable: false,
      fatal: true,
    },
    updated_at: now,
    created_at: record?.created_at || now,
  };
  fs.writeFileSync(
    paths.workflowJsonPath,
    `${JSON.stringify(next, null, 2)}\n`,
    "utf8"
  );
  return true;
}

/**
 * @param {string} jobRoot
 */
export function markJobCanceledByNode(jobRoot) {
  const paths = jobPathsFromRoot(jobRoot);
  const record = readWorkflowRecord(paths.workflowJsonPath);
  if (record && isTerminalJobStatus(record.status)) {
    return false;
  }
  const now = new Date().toISOString();
  const next = {
    ...(record || {}),
    status: "canceled",
    updated_at: now,
    created_at: record?.created_at || now,
  };
  fs.writeFileSync(
    paths.workflowJsonPath,
    `${JSON.stringify(next, null, 2)}\n`,
    "utf8"
  );
  return true;
}

/**
 * @param {string} jobRoot
 */
export function markCancelRequested(jobRoot) {
  const paths = jobPathsFromRoot(jobRoot);
  const record = readWorkflowRecord(paths.workflowJsonPath);
  if (record && isTerminalJobStatus(record.status)) {
    return false;
  }
  const now = new Date().toISOString();
  const next = {
    ...(record || {}),
    cancel_requested_at: now,
    updated_at: now,
  };
  fs.writeFileSync(
    paths.workflowJsonPath,
    `${JSON.stringify(next, null, 2)}\n`,
    "utf8"
  );
  return true;
}

/**
 * @param {string} jobRoot
 * @returns {boolean}
 */
export function shouldMarkFailedOnRunnerExit(jobRoot) {
  const paths = jobPathsFromRoot(jobRoot);
  const record = readWorkflowRecord(paths.workflowJsonPath);
  if (!record) return true;
  if (isTerminalJobStatus(record.status)) return false;
  return ["queued", "running"].includes(String(record.status));
}
