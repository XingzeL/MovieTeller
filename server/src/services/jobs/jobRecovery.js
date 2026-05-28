import fs from "node:fs";
import path from "node:path";

import { getJobsRoot, isTerminalJobStatus, jobPathsFromRoot } from "../../config/jobs.js";
import { markJobFailed, readWorkflowRecord } from "./jobProcess.js";

const RECOVERABLE_STATUSES = new Set(["queued", "running"]);

/**
 * Mark jobs left in a non-terminal in-memory state as failed after a server restart.
 * This avoids zombie jobs that can no longer be observed by the Node process.
 * @param {{ jobsRoot?: string }} [opts]
 */
export function recoverJobsOnStartup(opts = {}) {
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
    if (isTerminalJobStatus(status) || !RECOVERABLE_STATUSES.has(status)) {
      continue;
    }
    if (markJobFailed(jobRoot, {
      error_code: "server_restarted",
      message: `job was ${status} when the server started; mark as failed to avoid a zombie job`,
    })) {
      recovered += 1;
    }
  }
  return { scanned, recovered };
}
