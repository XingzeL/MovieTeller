import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";

import { jobPathsFromRoot } from "../../config/jobs.js";
import { getRepoRoot } from "../../config/index.js";
import { buildPythonEnv, resolveProjectPython } from "../pythonRuntime.js";
import { applyRunnerExit, applyRunnerSpawnError } from "./runnerExit.js";

const fakeRunnerScript = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../../scripts/fake-hanging-runner.mjs"
);

function shouldUseFakeHangingRunner() {
  if (process.env.MOVIE_TELLER_FAKE_HANGING_RUNNER !== "1") return false;
  return (
    process.env.NODE_ENV === "test" ||
    process.env.MOVIE_TELLER_ALLOW_FAKE_RUNNER === "1"
  );
}

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
  const stdoutFd = fs.openSync(paths.runnerStdoutPath, "a");
  const stderrFd = fs.openSync(paths.runnerStderrPath, "a");

  const runnerArgs = [
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
    runnerArgs.push("--user-id", userId);
  }

  /** @type {import('node:child_process').ChildProcess} */
  let child;
  if (shouldUseFakeHangingRunner()) {
    child = spawn(process.execPath, [fakeRunnerScript, ...runnerArgs], {
      cwd: repoRoot,
      detached: true,
      stdio: ["ignore", stdoutFd, stderrFd],
    });
  } else {
    const python = resolveProjectPython(repoRoot);
    const env = buildPythonEnv(repoRoot);
    child = spawn(
      python,
      ["-m", "movie_pipeline.job_runner", ...runnerArgs],
      {
        cwd: repoRoot,
        env,
        detached: true,
        stdio: ["ignore", stdoutFd, stderrFd],
      }
    );
  }

  child.on("error", (err) => {
    applyRunnerSpawnError(jobRoot, err);
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
    spawnedJobs.delete(jobId);
    applyRunnerExit(jobRoot, { code, signal });
  });

  child.unref();

  if (child.pid) {
    spawnedJobs.set(jobId, {
      pid: child.pid,
      spawnedAt: new Date().toISOString(),
    });
    fs.writeFileSync(
      paths.runnerPidPath,
      `${JSON.stringify({ pid: child.pid, spawnedAt: new Date().toISOString() })}\n`,
      "utf8"
    );
  }
  return child;
}
