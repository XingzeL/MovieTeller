import fs from "node:fs";

import { jobPathsFromRoot } from "../../config/jobs.js";
import {
  markJobCanceledByNode,
  markJobFailed,
  readWorkflowRecord,
  shouldMarkFailedOnRunnerExit,
} from "./jobProcess.js";

/**
 * @typedef {"none" | "mark_canceled" | "mark_failed"} RunnerExitAction
 */

/**
 * Decide how Node should react to a detached runner process exiting.
 * Does not read the child process itself — only workflow.json + cancel.flag.
 *
 * @param {string} jobRoot
 * @param {{ code: number | null, signal: NodeJS.Signals | null }} exit
 * @returns {{ action: RunnerExitAction, reason: string, applied: boolean }}
 */
export function applyRunnerExit(jobRoot, exit) {
  const paths = jobPathsFromRoot(jobRoot);
  const { code, signal } = exit;

  if (!shouldMarkFailedOnRunnerExit(jobRoot)) {
    const record = readWorkflowRecord(paths.workflowJsonPath);
    const status = record ? String(record.status) : "missing";
    return { action: "none", reason: `terminal_or_missing:${status}`, applied: false };
  }

  const successExit = code === 0 && !signal;
  if (successExit) {
    return { action: "none", reason: "exit_code_0", applied: false };
  }

  if (fs.existsSync(paths.cancelFlagPath)) {
    const applied = markJobCanceledByNode(jobRoot);
    return {
      action: "mark_canceled",
      reason: "cancel_flag_present",
      applied,
    };
  }

  const applied = markJobFailed(jobRoot, {
    error_code: "runner_exited",
    message: `workflow runner exited with code ${code}${signal ? ` signal ${signal}` : ""}`,
    exitCode: code,
  });
  return { action: "mark_failed", reason: "nonzero_exit", applied };
}

/**
 * @param {string} jobRoot
 * @param {{ message?: string }} err
 */
export function applyRunnerSpawnError(jobRoot, err) {
  const paths = jobPathsFromRoot(jobRoot);
  if (!shouldMarkFailedOnRunnerExit(jobRoot)) {
    return { action: "none", reason: "terminal_or_missing", applied: false };
  }
  if (fs.existsSync(paths.cancelFlagPath)) {
    const applied = markJobCanceledByNode(jobRoot);
    return { action: "mark_canceled", reason: "cancel_flag_present", applied };
  }
  const applied = markJobFailed(jobRoot, {
    error_code: "spawn_failed",
    message: String(err?.message || err),
  });
  return { action: "mark_failed", reason: "spawn_error", applied };
}
