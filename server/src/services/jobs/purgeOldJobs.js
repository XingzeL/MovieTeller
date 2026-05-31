import fs from "node:fs";
import path from "node:path";

import { getJobsRoot, isSafeJobId, isTerminalJobStatus } from "../../config/jobs.js";
import { scanAllJobsForSystem } from "./scanAllJobsForSystem.js";

const DEFAULT_MAX_AGE_DAYS = 3;

/**
 * 删除创建时间超过指定天数的全部旧任务（包括目录下所有文件：视频、学习卡、workflow.json、日志等）。
 * 仅删除已处于终态（succeeded/failed/canceled）的任务，正在运行或排队的任务不会被删除。
 *
 * @param {number} [maxAgeDays]
 * @param {{ jobsRoot?: string }} [opts]
 * @returns {{ deleted: number, scanned: number }}
 */
export function purgeOldJobs(maxAgeDays = DEFAULT_MAX_AGE_DAYS, opts = {}) {
  const jobsRoot = opts.jobsRoot || getJobsRoot();
  const scannedEntries = scanAllJobsForSystem({ jobsRoot });

  const cutoffMs = Date.now() - maxAgeDays * 24 * 60 * 60 * 1000;

  let scanned = 0;
  let deleted = 0;

  for (const { jobId, listItem: job } of scannedEntries) {
    scanned++;

    if (!isTerminalJobStatus(job.status)) {
      continue;
    }

    const created = job.createdAt || job.updatedAt;
    const createdMs = Date.parse(String(created || ""));
    if (!Number.isFinite(createdMs) || createdMs >= cutoffMs) {
      continue;
    }

    const jobRoot = path.join(jobsRoot, jobId);

    if (!isSafeJobId(jobId) || !fs.existsSync(jobRoot)) {
      continue;
    }

    try {
      fs.rmSync(jobRoot, { recursive: true, force: true });
      deleted++;
      console.log(
        `[Job Retention] Deleted job ${jobId} (created ${created}, age > ${maxAgeDays} days)`
      );
    } catch (err) {
      console.error(`[Job Retention] Failed to delete job directory ${jobId}`, err);
    }
  }

  if (deleted > 0) {
    console.log(
      `[Job Retention] Full purge completed: deleted ${deleted} jobs older than ${maxAgeDays} days (scanned ${scanned}).`
    );
  }

  return { deleted, scanned };
}
