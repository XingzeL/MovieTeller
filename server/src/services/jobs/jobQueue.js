import fs from "node:fs";

import { getJobsRoot, jobPathsFromRoot, resolveJobRoot } from "../../config/jobs.js";
import { createJobFromUpload, spawnPreparedJob } from "./createJob.js";
import {
  markCancelRequested,
  markJobCanceledByNode,
} from "./jobProcess.js";

const DEFAULT_MAX_RUNNING = 1;

/** @type {Set<string>} */
const running = new Set();

/** @type {Array<{ jobId: string, jobRoot: string, jobsRoot: string, videoPath: string, userId: string | null }>} */
const waiting = [];

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
  const paths = jobPathsFromRoot(resolveJobRoot(jobsRoot, jobId));
  const interval = setInterval(() => {
    try {
      if (!fs.existsSync(paths.workflowJsonPath)) return;
      const record = JSON.parse(fs.readFileSync(paths.workflowJsonPath, "utf8"));
      const terminal = ["succeeded", "failed", "canceled"].includes(record.status);
      if (!terminal) return;
      clearInterval(interval);
      running.delete(jobId);
      drainQueue();
    } catch {
      /* keep polling */
    }
  }, 2000);
}

function drainQueue() {
  while (running.size < maxRunningJobs() && waiting.length > 0) {
    const next = waiting.shift();
    if (!next) break;
    running.add(next.jobId);
    spawnPreparedJob(next);
    watchJobCompletion(next.jobId);
  }
}

/**
 * @param {{ file: import('multer').File, body: Record<string, unknown> }} input
 */
export function enqueueJobUpload(input) {
  const prepared = createJobFromUpload({ ...input, spawn: false });
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

/**
 * @param {string} jobId
 */
export function cancelJob(jobId) {
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
    drainQueue();
    return { jobId, status: "canceled" };
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
  running.clear();
  waiting.splice(0, waiting.length);
}

export function markJobRunningForTests(jobId) {
  running.add(jobId);
}

export function markJobWaitingForTests(prepared) {
  waiting.push(prepared);
}
