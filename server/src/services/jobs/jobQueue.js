/**
 * In-process memory queue (single Node process only).
 * Multi-instance deployments need Postgres SKIP LOCKED or BullMQ — see docs/job-queue-limitations.md.
 */
import fs from "node:fs";

import { getJobsRoot, jobPathsFromRoot, resolveJobRoot } from "../../config/jobs.js";
import { isDbEnabled } from "../../db/database.js";
import {
  getJobById,
  markJobCanceledQueued,
  markJobCanceling,
  retryJobInDb,
} from "../../db/jobsRepository.js";
import { isApiRunMode, isWorkerRunMode } from "../../runtime/runMode.js";
import { releaseClaimIfOwned } from "./claimJob.js";
import { createJobFromUpload, spawnPreparedJob } from "./createJob.js";
import { syncWorkflowTerminalToDb } from "./dbJobSync.js";
import {
  markCancelRequested,
  markJobCanceledByNode,
  readWorkflowRecord,
} from "./jobProcess.js";

const DEFAULT_MAX_RUNNING = 1;

/** @type {Set<string>} */
const running = new Set();

/** @type {Array<{ jobId: string, jobRoot: string, jobsRoot: string, videoPath: string, userId: string | null }>} */
const waiting = [];

/** @type {Map<string, NodeJS.Timeout>} */
const completionWatchers = new Map();

/** @type {Map<string, { attemptId: number, claimedBy: string, heartbeatTimer?: NodeJS.Timeout }>} */
const dbJobContexts = new Map();

/**
 * @param {string} jobId
 * @param {{ attemptId: number, claimedBy: string, heartbeatTimer?: NodeJS.Timeout }} ctx
 */
export function registerDbJobContext(jobId, ctx) {
  dbJobContexts.set(jobId, ctx);
}

/**
 * @param {string} jobId
 */
export function unregisterDbJobContext(jobId) {
  const ctx = dbJobContexts.get(jobId);
  if (ctx?.heartbeatTimer) {
    clearInterval(ctx.heartbeatTimer);
  }
  dbJobContexts.delete(jobId);
}

function maxRunningJobs() {
  const raw = process.env.MAX_RUNNING_JOBS;
  const parsed = raw ? Number(raw) : DEFAULT_MAX_RUNNING;
  return Number.isFinite(parsed) && parsed > 0 ? Math.floor(parsed) : DEFAULT_MAX_RUNNING;
}

/**
 * @param {string} jobId
 */
export function isJobWaitingInQueue(jobId) {
  return waiting.some((item) => item.jobId === jobId);
}

/**
 * @param {string} jobId
 */
export function isJobMarkedRunning(jobId) {
  return running.has(jobId);
}

/**
 * @param {string} jobId
 */
function watchJobCompletion(jobId) {
  const jobsRoot = getJobsRoot();
  const jobRoot = resolveJobRoot(jobsRoot, jobId);
  const paths = jobPathsFromRoot(jobRoot);
  const existing = completionWatchers.get(jobId);
  if (existing) {
    clearInterval(existing);
  }
  const interval = setInterval(() => {
    try {
      if (!fs.existsSync(paths.workflowJsonPath)) return;
      const record = JSON.parse(fs.readFileSync(paths.workflowJsonPath, "utf8"));
      const terminal = ["succeeded", "failed", "canceled"].includes(record.status);
      if (!terminal) return;
      clearInterval(interval);
      completionWatchers.delete(jobId);
      running.delete(jobId);
      const dbCtx = dbJobContexts.get(jobId);
      if (dbCtx && isDbEnabled()) {
        syncWorkflowTerminalToDb(jobRoot, dbCtx).catch((err) => {
          console.error(`[jobQueue] db reconcile failed for ${jobId}`, err);
        });
        unregisterDbJobContext(jobId);
      }
      try {
        releaseClaimIfOwned(jobRoot);
      } catch {
        /* ignore */
      }
      drainQueue();
    } catch {
      /* keep polling */
    }
  }, 2000);
  completionWatchers.set(jobId, interval);
}

function drainQueue() {
  if (isApiRunMode() || isWorkerRunMode()) return;
  while (running.size < maxRunningJobs() && waiting.length > 0) {
    const next = waiting.shift();
    if (!next) break;
    running.add(next.jobId);
    spawnPreparedJob(next);
    watchJobCompletion(next.jobId);
  }
}

/**
 * @param {{ file: import('multer').File, body: Record<string, unknown>, userId: string }} input
 */
export async function enqueueJobUpload(input) {
  const prepared = await createJobFromUpload({
    file: input.file,
    body: input.body,
    userId: input.userId,
    spawn: false,
  });
  if (isApiRunMode() || isWorkerRunMode()) {
    return {
      jobId: prepared.jobId,
      status: "queued",
      createdAt: prepared.createdAt,
      outputRoot: prepared.outputRoot,
    };
  }
  if (running.size < maxRunningJobs()) {
    running.add(prepared.jobId);
    spawnPreparedJob(prepared);
    watchJobCompletion(prepared.jobId);
    return {
      jobId: prepared.jobId,
      status: "queued",
      createdAt: prepared.createdAt,
      outputRoot: prepared.outputRoot,
    };
  }
  waiting.push({
    jobId: prepared.jobId,
    jobRoot: prepared.jobRoot,
    jobsRoot: prepared.jobsRoot,
    videoPath: prepared.videoPath,
    userId: prepared.userId,
  });
  return {
    jobId: prepared.jobId,
    status: "queued",
    createdAt: prepared.createdAt,
    outputRoot: prepared.outputRoot,
  };
}

const RETRYABLE_STATUSES = new Set(["failed", "canceled"]);

/**
 * Re-queue an existing job directory (failed/canceled) without re-uploading.
 * @param {string} jobId
 * @param {string | null} [authUserId] authenticated owner (DB mode)
 */
export async function requeueExistingJob(jobId, authUserId = null) {
  const jobsRoot = getJobsRoot();
  const jobRoot = resolveJobRoot(jobsRoot, jobId);
  const paths = jobPathsFromRoot(jobRoot);
  const record = readWorkflowRecord(paths.workflowJsonPath);
  if (!record) {
    const err = new Error("job not found");
    err.statusCode = 404;
    throw err;
  }

  if (isJobMarkedRunning(jobId) || isJobWaitingInQueue(jobId)) {
    const err = new Error("job is already queued or running");
    err.statusCode = 409;
    throw err;
  }

  const videoPath = String(record.input_video_path || "");
  if (!videoPath || !fs.existsSync(videoPath)) {
    const err = new Error("input video missing; cannot retry");
    err.statusCode = 400;
    throw err;
  }

  if (fs.existsSync(paths.cancelFlagPath)) {
    fs.unlinkSync(paths.cancelFlagPath);
  }

  const now = new Date().toISOString();

  if (isDbEnabled()) {
    const userId =
      typeof authUserId === "string" && authUserId.trim()
        ? authUserId.trim()
        : record.user_id;
    if (typeof userId !== "string" || !userId) {
      const err = new Error("job not found");
      err.statusCode = 404;
      throw err;
    }
    await retryJobInDb(userId, jobId);
  } else {
    const status = String(record.status || "");
    if (!RETRYABLE_STATUSES.has(status)) {
      const err = new Error(`cannot retry job in status "${status}"`);
      err.statusCode = 409;
      throw err;
    }
  }

  const next = {
    ...record,
    status: "queued",
    error: null,
    current_stage: null,
    updated_at: now,
  };
  delete next.cancel_requested_at;
  fs.writeFileSync(
    paths.workflowJsonPath,
    `${JSON.stringify(next, null, 2)}\n`,
    "utf8"
  );

  const prepared = {
    jobId,
    jobRoot,
    jobsRoot,
    videoPath,
    userId: record.user_id ?? null,
  };

  if (isApiRunMode() || isWorkerRunMode()) {
    return { jobId, status: "queued", retriedAt: now };
  }

  if (running.size < maxRunningJobs()) {
    running.add(jobId);
    spawnPreparedJob(prepared);
    watchJobCompletion(jobId);
  } else {
    waiting.push(prepared);
  }

  return { jobId, status: "queued", retriedAt: now };
}

/**
 * @param {string} jobId
 */
export async function cancelJob(jobId, userId = null) {
  const jobsRoot = getJobsRoot();
  const jobRoot = resolveJobRoot(jobsRoot, jobId);
  const paths = jobPathsFromRoot(jobRoot);

  const inWaiting = isJobWaitingInQueue(jobId);
  const wasSpawned = isJobMarkedRunning(jobId);

  const waitingIdx = waiting.findIndex((item) => item.jobId === jobId);
  if (waitingIdx >= 0) {
    waiting.splice(waitingIdx, 1);
  }

  if (inWaiting && !wasSpawned) {
    markJobCanceledByNode(jobRoot);
    if (isDbEnabled() && userId) {
      await markJobCanceledQueued(userId, jobId);
    }
    drainQueue();
    return { jobId, status: "canceled" };
  }

  if (isDbEnabled() && userId) {
    const dbRow = await getJobById(jobId);
    if (dbRow && String(dbRow.status) === "queued") {
      markJobCanceledByNode(jobRoot);
      await markJobCanceledQueued(userId, jobId);
      drainQueue();
      return { jobId, status: "canceled" };
    }
    if (dbRow && String(dbRow.status) === "running") {
      const updated = await markJobCanceling(userId, jobId);
      if (updated) {
        markCancelRequested(jobRoot);
        return { jobId, status: "canceling" };
      }
    }
    if (dbRow && String(dbRow.status) === "canceling") {
      return { jobId, status: "canceling" };
    }
  }

  fs.writeFileSync(paths.cancelFlagPath, `${new Date().toISOString()}\n`, "utf8");
  markCancelRequested(jobRoot);

  return { jobId, status: "cancel_requested" };
}

export function getJobQueueSnapshot() {
  return {
    running: Array.from(running),
    waiting: waiting.map((item) => item.jobId),
    maxRunning: maxRunningJobs(),
  };
}

export function clearJobQueueForTests() {
  for (const timer of completionWatchers.values()) {
    clearInterval(timer);
  }
  completionWatchers.clear();
  running.clear();
  waiting.splice(0, waiting.length);
}

export function markJobRunningForTests(jobId) {
  running.add(jobId);
}

export function markJobWaitingForTests(prepared) {
  waiting.push(prepared);
}

/**
 * Reserve a running slot (worker loop). Caller must spawn or release on failure.
 * @param {{ jobId: string, jobRoot: string }} prepared
 */
export function tryAcquireQueueSlot(prepared) {
  if (running.size >= maxRunningJobs()) return false;
  if (running.has(prepared.jobId)) return false;
  running.add(prepared.jobId);
  watchJobCompletion(prepared.jobId);
  return true;
}

/**
 * Drop in-memory running slot and completion watcher only (no worker.lock).
 * @param {string} jobId
 */
export function releaseQueueSlotOnly(jobId) {
  running.delete(jobId);
  const existing = completionWatchers.get(jobId);
  if (existing) {
    clearInterval(existing);
    completionWatchers.delete(jobId);
  }
}

/**
 * Release running slot/watcher and this process's claim, if any.
 * @param {string} jobId
 * @param {string} [jobRoot]
 */
export function releaseQueueSlotAndClaim(jobId, jobRoot) {
  releaseQueueSlotOnly(jobId);
  if (jobRoot) {
    try {
      releaseClaimIfOwned(jobRoot);
    } catch {
      /* ignore */
    }
  }
}

/** @deprecated Prefer releaseQueueSlotOnly or releaseQueueSlotAndClaim */
export function releaseQueueSlot(jobId, jobRoot) {
  releaseQueueSlotAndClaim(jobId, jobRoot);
}
