import fs from "node:fs";
import path from "node:path";

import { getJobsRoot, isSafeJobId, isTerminalJobStatus } from "../../config/jobs.js";
import { listJobs } from "./listJobs.js";

const DEFAULT_MAX_AGE_DAYS = 3;

/**
 * 删除创建时间超过指定天数的全部旧任务（包括目录下所有文件：视频、学习卡、workflow.json、日志等）。
 * 仅删除已处于终态（succeeded/failed/canceled）的任务，正在运行或排队的任务不会被删除。
 *
 * @param {number} [maxAgeDays]
 * @returns {{ deleted: number, scanned: number }}
 */
export function purgeOldJobs(maxAgeDays = DEFAULT_MAX_AGE_DAYS) {
  const jobsRoot = getJobsRoot();

  // 拉取一个很大的数量，目标是拿到全部历史任务
  const { jobs } = listJobs({ limit: 10000 });

  const cutoffMs = Date.now() - maxAgeDays * 24 * 60 * 60 * 1000;

  let scanned = 0;
  let deleted = 0;

  for (const job of jobs) {
    scanned++;

    if (!isTerminalJobStatus(job.status)) {
      // 正在进行中的任务不删除
      continue;
    }

    const created = job.createdAt || job.updatedAt;
    const createdMs = Date.parse(String(created || ""));
    if (!Number.isFinite(createdMs) || createdMs >= cutoffMs) {
      // 还没到保留期
      continue;
    }

    const jobRoot = path.join(jobsRoot, job.jobId);

    if (!isSafeJobId(job.jobId) || !fs.existsSync(jobRoot)) {
      continue;
    }

    try {
      fs.rmSync(jobRoot, { recursive: true, force: true });
      deleted++;
      console.log(
        `[Job Retention] Deleted job ${job.jobId} (created ${created}, age > ${maxAgeDays} days)`
      );
    } catch (err) {
      console.error(`[Job Retention] Failed to delete job directory ${job.jobId}`, err);
    }
  }

  if (deleted > 0) {
    console.log(
      `[Job Retention] Full purge completed: deleted ${deleted} jobs older than ${maxAgeDays} days (scanned ${scanned}).`
    );
  }

  return { deleted, scanned };
}
