import fs from "node:fs";

import { getJobsRoot, jobPathsFromRoot, resolveJobRoot } from "../config/jobs.js";
import { isDbEnabled } from "../db/database.js";
import {
  claimNextQueuedJob,
  failJobByWorker,
  sweepStaleJobs,
  touchJobHeartbeat,
} from "../db/jobsRepository.js";
import { claimAndSpawn } from "../services/jobs/claimJob.js";
import { releaseClaim } from "../services/jobs/claimJob.js";
import { markWorkflowFailed, readWorkflowRecord } from "../services/jobs/jobProcess.js";
import {
  getJobQueueSnapshot,
  isJobMarkedRunning,
  registerDbJobContext,
  releaseQueueSlotAndClaim,
  releaseQueueSlotOnly,
  tryAcquireQueueSlot,
  unregisterDbJobContext,
} from "../services/jobs/jobQueue.js";
import { ensureCancelFlagForDbJob } from "../services/jobs/dbJobSync.js";
import { getWorkerId } from "../services/jobs/workerId.js";
import { reconcileOrphanRunningJobs } from "./startupRecovery.js";
import { scanAllJobsForSystem } from "../services/jobs/scanAllJobsForSystem.js";

/** @type {ReturnType<typeof setInterval> | null} */
let workerInterval = null;

function utcNowIso() {
  return new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
}

/**
 * @param {string} jobRoot
 */
function markWorkflowRunningOnDisk(jobRoot) {
  const paths = jobPathsFromRoot(jobRoot);
  if (!fs.existsSync(paths.workflowJsonPath)) return;
  const record = JSON.parse(fs.readFileSync(paths.workflowJsonPath, "utf8"));
  record.status = "running";
  record.updated_at = utcNowIso();
  fs.writeFileSync(
    paths.workflowJsonPath,
    `${JSON.stringify(record, null, 2)}\n`,
    "utf8"
  );
}

/**
 * @param {{ jobId: string, jobRoot: string, attemptId: number, claimedBy: string }} ctx
 */
function startDbHeartbeat(ctx) {
  const intervalMs = Number(process.env.HEARTBEAT_INTERVAL_MS || 30_000);
  const timer = setInterval(() => {
    touchJobHeartbeat({
      jobId: ctx.jobId,
      attemptId: ctx.attemptId,
      claimedBy: ctx.claimedBy,
    }).catch((err) => {
      console.error(`[queueWorker] heartbeat failed for ${ctx.jobId}`, err);
    });
    ensureCancelFlagForDbJob(ctx.jobId, ctx.jobRoot, ctx).catch((err) => {
      console.error(`[queueWorker] cancel ack failed for ${ctx.jobId}`, err);
    });
  }, intervalMs);
  registerDbJobContext(ctx.jobId, { ...ctx, heartbeatTimer: timer });
}

/**
 * @param {{ jobsRoot?: string }} [opts]
 */
async function tickOnceFromDatabase(opts = {}) {
  const jobsRoot = opts.jobsRoot || getJobsRoot();
  await sweepStaleJobs();

  const { running, maxRunning } = getJobQueueSnapshot();
  if (running.length >= maxRunning) return { picked: 0 };

  const claimed = await claimNextQueuedJob(getWorkerId());
  if (!claimed) return { picked: 0 };

  const jobId = String(claimed.job_id);
  const jobRoot = String(claimed.output_root);
  const videoPath = String(claimed.input_video_path || "");
  const workerCtx = {
    jobId,
    attemptId: Number(claimed.attempt_id ?? 1),
    claimedBy: String(claimed.claimed_by || getWorkerId()),
  };

  /**
   * @param {string} errorCode
   * @param {string} errorMessage
   */
  async function failPrepare(errorCode, errorMessage) {
    markWorkflowFailed(jobRoot, { errorCode, errorMessage, retryable: true });
    await failJobByWorker({
      ...workerCtx,
      errorCode,
      errorMessage,
      retryable: true,
    });
  }

  if (!videoPath || !fs.existsSync(videoPath)) {
    console.error(`[queueWorker] missing input video for ${jobId}`);
    await failPrepare("worker_prepare_failed", "Input video missing");
    return { picked: 0 };
  }

  markWorkflowRunningOnDisk(jobRoot);

  const prepared = {
    jobId,
    jobRoot,
    jobsRoot,
    videoPath,
    userId: claimed.user_id ?? null,
    attemptId: workerCtx.attemptId,
    claimedBy: workerCtx.claimedBy,
  };

  if (!tryAcquireQueueSlot(prepared)) {
    await failPrepare("worker_prepare_failed", "Could not acquire local queue slot");
    return { picked: 0 };
  }

  try {
    if (!claimAndSpawn(prepared)) {
      releaseQueueSlotOnly(prepared.jobId);
      await failPrepare("spawn_failed", "Failed to claim job directory or spawn runner");
      return { picked: 0 };
    }
    startDbHeartbeat({
      jobId: prepared.jobId,
      jobRoot: prepared.jobRoot,
      attemptId: prepared.attemptId,
      claimedBy: prepared.claimedBy,
    });
    return { picked: 1 };
  } catch (err) {
    releaseQueueSlotAndClaim(prepared.jobId, prepared.jobRoot);
    unregisterDbJobContext(prepared.jobId);
    console.error(`[queueWorker] claimAndSpawn failed for ${prepared.jobId}`, err);
    await failPrepare(
      "spawn_failed",
      err instanceof Error ? err.message : "claimAndSpawn threw"
    );
    return { picked: 0 };
  }
}

/**
 * @param {{ jobsRoot?: string }} [opts]
 */
function tickOnceFromFilesystem(opts = {}) {
  const jobsRoot = opts.jobsRoot || getJobsRoot();
  reconcileOrphanRunningJobs({ jobsRoot });

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
    try {
      if (!claimAndSpawn(prepared)) {
        releaseQueueSlotOnly(prepared.jobId);
        continue;
      }
      picked += 1;
    } catch (err) {
      releaseQueueSlotAndClaim(prepared.jobId, prepared.jobRoot);
      console.error(
        `[queueWorker] claimAndSpawn failed for ${prepared.jobId}`,
        err
      );
    }
  }
  return { picked };
}

/**
 * @param {{ jobsRoot?: string }} [opts]
 */
export async function tickOnce(opts = {}) {
  if (isDbEnabled()) {
    return tickOnceFromDatabase(opts);
  }
  return tickOnceFromFilesystem(opts);
}

/**
 * @param {{ pollMs?: number }} [opts]
 */
export function startWorkerLoop(opts = {}) {
  const pollMs = opts.pollMs ?? 2000;
  if (workerInterval) clearInterval(workerInterval);
  workerInterval = setInterval(() => {
    tickOnce().catch((err) => {
      console.error("[queueWorker] tick failed", err);
    });
  }, pollMs);
  tickOnce().catch((err) => {
    console.error("[queueWorker] initial tick failed", err);
  });
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

export { releaseClaim, unregisterDbJobContext };
