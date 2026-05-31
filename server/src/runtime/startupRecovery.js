import fs from "node:fs";
import path from "node:path";

import { getJobsRoot, isTerminalJobStatus, jobPathsFromRoot } from "../config/jobs.js";
import { markJobFailed, readWorkflowRecord } from "../services/jobs/jobProcess.js";
import { recoverJobsOnStartup } from "../services/jobs/jobRecovery.js";
import { isWorkerRunMode, isCombinedRunMode } from "./runMode.js";

const RECOVERABLE_COMBINED = new Set(["queued", "running"]);

/**
 * Combined / default: existing behavior (queued + running → failed).
 * @param {{ jobsRoot?: string }} [opts]
 */
export function recoverForCombined(opts = {}) {
  if (!isCombinedRunMode()) {
    return { scanned: 0, recovered: 0, skipped: true };
  }
  return recoverJobsOnStartup(opts);
}

/**
 * @param {number} pid
 */
function processAlive(pid) {
  if (!pid || !Number.isFinite(pid)) return false;
  try {
    process.kill(pid, 0);
    return true;
  } catch (err) {
    return err && typeof err === "object" && "code" in err && err.code === "EPERM";
  }
}

/**
 * @param {string} jobRoot
 */
function isRunnerAlive(jobRoot) {
  const paths = jobPathsFromRoot(jobRoot);
  const pidPath = paths.runnerPidPath;
  if (fs.existsSync(pidPath)) {
    try {
      const payload = JSON.parse(fs.readFileSync(pidPath, "utf8"));
      if (processAlive(Number(payload.pid))) return true;
    } catch {
      /* fall through */
    }
  }
  return false;
}

/**
 * Mark running jobs whose runner.pid is missing or dead (worker + periodic tick).
 * @param {{ jobsRoot?: string }} [opts]
 */
export function reconcileOrphanRunningJobs(opts = {}) {
  const jobsRoot = opts.jobsRoot || getJobsRoot();
  if (!fs.existsSync(jobsRoot)) {
    return { scanned: 0, recovered: 0 };
  }

  let scanned = 0;
  let recovered = 0;
  for (const name of fs.readdirSync(jobsRoot)) {
    const jobRoot = path.join(jobsRoot, name);
    let stat;
    try {
      stat = fs.statSync(jobRoot);
    } catch {
      continue;
    }
    if (!stat.isDirectory()) continue;

    const paths = jobPathsFromRoot(jobRoot);
    const record = readWorkflowRecord(paths.workflowJsonPath);
    if (!record) continue;
    scanned += 1;

    const status = String(record.status || "");
    if (status !== "running" || isTerminalJobStatus(status)) continue;
    if (isRunnerAlive(jobRoot)) continue;

    if (
      markJobFailed(jobRoot, {
        error_code: "server_restarted_or_orphan",
        message: "runner not alive (orphan running job)",
      })
    ) {
      recovered += 1;
    }
  }
  return { scanned, recovered };
}

/**
 * Worker: only fail orphan `running` jobs whose runner is gone. Leave `queued` for pickup.
 * @param {{ jobsRoot?: string }} [opts]
 */
export function recoverForWorker(opts = {}) {
  if (!isWorkerRunMode()) {
    return { scanned: 0, recovered: 0, skipped: true };
  }
  return reconcileOrphanRunningJobs(opts);
}

/**
 * @param {{ jobsRoot?: string }} [opts]
 */
export function runStartupRecovery(opts = {}) {
  if (isWorkerRunMode()) {
    return recoverForWorker(opts);
  }
  if (isCombinedRunMode()) {
    return recoverForCombined(opts);
  }
  return { scanned: 0, recovered: 0, skipped: true };
}

export { RECOVERABLE_COMBINED };
