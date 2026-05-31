import fs from "node:fs";
import path from "node:path";

import { getJobsRoot, isSafeJobId, jobPathsFromRoot } from "../../config/jobs.js";
import { readWorkflowRecord } from "./jobProcess.js";
import { readJobRequestMetadata } from "./readJobRequest.js";
import { jobRecordToListItemDto } from "./readJob.js";

/**
 * Full filesystem scan for retention/recovery/admin — not subject to API list MAX_LIMIT.
 * @param {{ jobsRoot?: string }} [opts]
 * @returns {Array<{ jobId: string, record: Record<string, unknown>, jobRoot: string, listItem: ReturnType<typeof jobRecordToListItemDto> }>}
 */
export function scanAllJobsForSystem(opts = {}) {
  const jobsRoot = opts.jobsRoot || getJobsRoot();
  if (!fs.existsSync(jobsRoot)) {
    return [];
  }

  const entries = [];
  for (const name of fs.readdirSync(jobsRoot)) {
    if (!isSafeJobId(name)) continue;
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

    const jobId = String(record.job_id || name);
    entries.push({
      jobId,
      record,
      jobRoot,
      listItem: jobRecordToListItemDto(
        record,
        readJobRequestMetadata(jobRoot),
        jobRoot
      ),
    });
  }
  return entries;
}
