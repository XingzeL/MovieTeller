import fs from "node:fs";
import os from "node:os";
import path from "node:path";

import { jobPathsFromRoot } from "../../config/jobs.js";
import { readWorkflowRecord } from "./jobProcess.js";
import { spawnPreparedJob } from "./createJob.js";

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
 * @param {string} lockPath
 */
function isStaleLock(lockPath) {
  if (!fs.existsSync(lockPath)) return true;
  let payload;
  try {
    payload = JSON.parse(fs.readFileSync(lockPath, "utf8"));
  } catch {
    return true;
  }
  if (!processAlive(Number(payload.pid))) return true;

  const jobRoot = path.dirname(path.dirname(lockPath));
  const paths = jobPathsFromRoot(jobRoot);
  const record = readWorkflowRecord(paths.workflowJsonPath);
  const claimedAt = Date.parse(String(payload.claimedAt || ""));
  if (
    record &&
    String(record.status) === "queued" &&
    Number.isFinite(claimedAt) &&
    claimedAt + 30 * 60 * 1000 < Date.now()
  ) {
    return true;
  }
  return false;
}

/**
 * @param {string} jobId
 * @param {string} jobRoot
 */
export function tryClaim(jobId, jobRoot) {
  const paths = jobPathsFromRoot(jobRoot);
  const lockPath = paths.workerLockPath;
  const body = JSON.stringify({
    pid: process.pid,
    hostname: os.hostname(),
    jobId,
    claimedAt: new Date().toISOString(),
  });

  const writeExclusive = () => {
    fs.writeFileSync(lockPath, `${body}\n`, { flag: "wx" });
    return true;
  };

  try {
    return writeExclusive();
  } catch (err) {
    if (err && typeof err === "object" && "code" in err && err.code !== "EEXIST") {
      throw err;
    }
    if (!isStaleLock(lockPath)) return false;
    try {
      fs.unlinkSync(lockPath);
    } catch {
      return false;
    }
    try {
      return writeExclusive();
    } catch {
      return false;
    }
  }
}

/**
 * @param {string} jobRoot
 */
export function releaseClaim(jobRoot) {
  const paths = jobPathsFromRoot(jobRoot);
  if (fs.existsSync(paths.workerLockPath)) {
    fs.unlinkSync(paths.workerLockPath);
  }
}

/**
 * @param {{ jobId: string, jobRoot: string, jobsRoot: string, videoPath: string, userId?: string | null }} prepared
 */
export function claimAndSpawn(prepared) {
  if (!tryClaim(prepared.jobId, prepared.jobRoot)) {
    return false;
  }
  try {
    spawnPreparedJob(prepared);
    return true;
  } catch (err) {
    releaseClaim(prepared.jobRoot);
    throw err;
  }
}
