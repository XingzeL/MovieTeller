import fs from "node:fs";
import path from "node:path";

import { getJobsRoot, jobPathsFromRoot, resolveJobRoot } from "../config/jobs.js";
import { claimAndSpawn } from "../services/jobs/claimJob.js";
import { releaseClaim } from "../services/jobs/claimJob.js";
import { readWorkflowRecord } from "../services/jobs/jobProcess.js";
import {
  getJobQueueSnapshot,
  isJobMarkedRunning,
  releaseQueueSlot,
  tryAcquireQueueSlot,
} from "../services/jobs/jobQueue.js";
import { scanAllJobsForSystem } from "../services/jobs/scanAllJobsForSystem.js";

/** @type {ReturnType<typeof setInterval> | null} */
let workerInterval = null;

/**
 * @param {{ jobsRoot?: string }} [opts]
 */
export function tickOnce(opts = {}) {
  const jobsRoot = opts.jobsRoot || getJobsRoot();
  const { running, maxRunning } = getJobQueueSnapshot();
  if (running.length >= maxRunning) return { picked: 0 };

  const candidates = scanAllJobsForSystem({ jobsRoot })
    .filter((job) => String(job.record.status || "") === "queued")
    .filter((job) => {
      const paths = jobPathsFromRoot(job.jobRoot);
      return !fs.existsSync(paths.cancelFlagPath);
    })
    .sort((a, b) => {
      const ca = Date.parse(String(a.record.created_at || "")) || 0;
      const cb = Date.parse(String(b.record.created_at || "")) || 0;
      return ca - cb;
    });

  let picked = 0;
  for (const job of candidates) {
    if (getJobQueueSnapshot().running.length >= maxRunning) break;
    if (isJobMarkedRunning(job.jobId)) continue;

    const jobRoot = resolveJobRoot(jobsRoot, job.jobId);
    const paths = jobPathsFromRoot(jobRoot);
    const record = readWorkflowRecord(paths.workflowJsonPath);
    if (!record) continue;
    const videoPath = String(record.input_video_path || "");
    if (!videoPath || !fs.existsSync(videoPath)) continue;

    const prepared = {
      jobId: job.jobId,
      jobRoot,
      jobsRoot,
      videoPath,
      userId: record.user_id ?? null,
    };

    if (!tryAcquireQueueSlot(prepared)) continue;
    if (!claimAndSpawn(prepared)) {
      releaseQueueSlot(prepared.jobId, prepared.jobRoot);
      continue;
    }
    picked += 1;
  }
  return { picked };
}

/**
 * @param {{ pollMs?: number }} [opts]
 */
export function startWorkerLoop(opts = {}) {
  const pollMs = opts.pollMs ?? 2000;
  if (workerInterval) clearInterval(workerInterval);
  workerInterval = setInterval(() => {
    try {
      tickOnce();
    } catch (err) {
      console.error("[queueWorker] tick failed", err);
    }
  }, pollMs);
  return { pollMs };
}

/**
 * @param {{ pollMs?: number } | null} handle
 */
export function stopWorkerLoop(handle = null) {
  if (workerInterval) {
    clearInterval(workerInterval);
    workerInterval = null;
  }
  void handle;
}

export { releaseClaim };
