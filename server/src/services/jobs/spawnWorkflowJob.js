import fs from "node:fs";
import { spawn } from "node:child_process";

import { jobPathsFromRoot } from "../../config/jobs.js";
import { getRepoRoot } from "../../config/index.js";
import { buildPythonEnv, resolveProjectPython } from "../pythonRuntime.js";
import {
  markJobFailed,
  shouldMarkFailedOnRunnerExit,
} from "./jobProcess.js";

/** @type {Map<string, { pid: number, spawnedAt: string }>} */
export const spawnedJobs = new Map();

/**
 * @param {{ jobsRoot: string, jobId: string, jobRoot: string, videoPath: string, userId?: string | null }} opts
 */
export function spawnWorkflowJob(opts) {
  const { jobsRoot, jobId, jobRoot, videoPath, userId } = opts;
  const paths = jobPathsFromRoot(jobRoot);
  fs.mkdirSync(paths.logsDir, { recursive: true });

  const repoRoot = getRepoRoot();
  const python = resolveProjectPython(repoRoot);
  const env = buildPythonEnv(repoRoot);
  const args = [
    "-m",
    "movie_pipeline.job_runner",
    "--job-id",
    jobId,
    "--jobs-root",
    jobsRoot,
    "--video",
    videoPath,
    "--request-json",
    paths.requestJsonPath,
  ];
  if (userId) {
    args.push("--user-id", userId);
  }

  const stdoutFd = fs.openSync(paths.runnerStdoutPath, "a");
  const stderrFd = fs.openSync(paths.runnerStderrPath, "a");

  const child = spawn(python, args, {
    cwd: repoRoot,
    env,
    detached: true,
    stdio: ["ignore", stdoutFd, stderrFd],
  });

  child.on("error", (err) => {
    if (shouldMarkFailedOnRunnerExit(jobRoot)) {
      markJobFailed(jobRoot, {
        error_code: "spawn_failed",
        message: String(err?.message || err),
      });
    }
  });

  child.on("exit", (code, signal) => {
    try {
      fs.closeSync(stdoutFd);
    } catch {
      /* ignore */
    }
    try {
      fs.closeSync(stderrFd);
    } catch {
      /* ignore */
    }
    if (code === 0) return;
    if (!shouldMarkFailedOnRunnerExit(jobRoot)) return;
    markJobFailed(jobRoot, {
      error_code: "runner_exited",
      message: `workflow runner exited with code ${code}${signal ? ` signal ${signal}` : ""}`,
      exitCode: code,
    });
  });

  child.unref();

  if (child.pid) {
    spawnedJobs.set(jobId, {
      pid: child.pid,
      spawnedAt: new Date().toISOString(),
    });
  }
  return child;
}
