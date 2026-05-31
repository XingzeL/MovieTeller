import fs from "fs";
import path from "path";

import { getRepoRoot } from "./index.js";

/**
 * @param {string} jobsRoot absolute path
 * @returns {{ ok: true, absRoot: string } | { ok: false, error: string }}
 */
export function validateJobsRootInsideRepo(jobsRoot) {
  const repoRoot = getRepoRoot();
  const absRoot = path.resolve(jobsRoot);
  const rel = path.relative(repoRoot, absRoot);
  if (rel.startsWith("..") || path.isAbsolute(rel)) {
    return { ok: false, error: "jobs root must be inside the repository" };
  }
  return { ok: true, absRoot };
}

/** @returns {string} absolute jobs root */
export function getJobsRoot() {
  const repoRoot = getRepoRoot();
  const configured = process.env.JOBS_ROOT?.trim();
  const jobsRoot = configured
    ? path.resolve(configured)
    : path.join(repoRoot, "artifacts", "jobs");
  const check = validateJobsRootInsideRepo(jobsRoot);
  if (!check.ok) {
    throw new Error(check.error);
  }
  fs.mkdirSync(check.absRoot, { recursive: true });
  return check.absRoot;
}

/**
 * @param {string} jobId
 * @returns {boolean}
 */
export function isSafeJobId(jobId) {
  const text = String(jobId || "").trim();
  if (!text) return false;
  if (text === "." || text === "..") return false;
  if (text.includes("/") || text.includes("\\")) return false;
  return true;
}

/**
 * @param {string} jobsRoot
 * @param {string} jobId
 */
export function resolveJobRoot(jobsRoot, jobId) {
  if (!isSafeJobId(jobId)) {
    throw new Error("invalid job id");
  }
  return path.join(jobsRoot, jobId);
}

/**
 * @param {string} jobRoot
 */
export function jobPathsFromRoot(jobRoot) {
  const root = path.resolve(jobRoot);
  return {
    root,
    inputDir: path.join(root, "input"),
    logsDir: path.join(root, "logs"),
    workflowJsonPath: path.join(root, "workflow.json"),
    workflowLogPath: path.join(root, "logs", "workflow.jsonl"),
    requestJsonPath: path.join(root, "request.json"),
    cancelFlagPath: path.join(root, "cancel.flag"),
    runnerStdoutPath: path.join(root, "logs", "runner.stdout.log"),
    runnerStderrPath: path.join(root, "logs", "runner.stderr.log"),
    runnerPidPath: path.join(root, "logs", "runner.pid"),
    workerLockPath: path.join(root, "worker.lock"),
    artifactManifestPath: path.join(root, "artifacts", "manifest.json"),
  };
}

/** @param {string} status */
export function isTerminalJobStatus(status) {
  return ["succeeded", "failed", "canceled"].includes(String(status || ""));
}
