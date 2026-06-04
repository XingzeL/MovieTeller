import fs from "node:fs";

import { jobPathsFromRoot } from "../../config/jobs.js";

/**
 * @typedef {'killed' | 'already_exited' | 'skipped_windows' | 'no_pid' | 'failed'} KillProcessGroupOutcome
 */

/**
 * @param {string} jobRoot
 * @returns {number | null}
 */
export function readRunnerPid(jobRoot) {
  const paths = jobPathsFromRoot(jobRoot);
  if (!fs.existsSync(paths.runnerPidPath)) return null;
  try {
    const payload = JSON.parse(fs.readFileSync(paths.runnerPidPath, "utf8"));
    const pid = Number(payload.pid);
    return Number.isFinite(pid) && pid > 0 ? pid : null;
  } catch {
    return null;
  }
}

/**
 * @param {number} pid
 */
export function isProcessAlive(pid) {
  if (!pid || !Number.isFinite(pid)) return false;
  try {
    process.kill(pid, 0);
    return true;
  } catch (err) {
    return (
      err &&
      typeof err === "object" &&
      "code" in err &&
      err.code === "EPERM"
    );
  }
}

/**
 * POSIX: send signal to process group via negative pid (detached spawn session leader).
 *
 * @param {number} pid
 * @param {{
 *   killFn?: (pid: number, signal: NodeJS.Signals) => void,
 *   isAliveFn?: (pid: number) => boolean,
 *   graceMs?: number,
 *   postKillPollMs?: number,
 *   sleepFn?: (ms: number) => Promise<void>,
 * }} [opts]
 * @returns {Promise<{ outcome: KillProcessGroupOutcome }>}
 */
export async function killProcessGroup(pid, opts = {}) {
  if (process.platform === "win32") {
    return { outcome: "skipped_windows" };
  }
  if (!pid || !Number.isFinite(pid)) {
    return { outcome: "no_pid" };
  }

  const killFn = opts.killFn ?? ((p, sig) => process.kill(p, sig));
  const isAliveFn = opts.isAliveFn ?? isProcessAlive;
  const graceMs =
    opts.graceMs ?? Number(process.env.FORCED_CANCEL_KILL_GRACE_MS || 30_000);
  const sleepFn =
    opts.sleepFn ??
    ((ms) => new Promise((resolve) => setTimeout(resolve, ms)));

  const pgid = -pid;

  if (!isAliveFn(pid)) {
    return { outcome: "already_exited" };
  }

  try {
    killFn(pgid, "SIGTERM");
  } catch (err) {
    if (err && typeof err === "object" && "code" in err && err.code === "ESRCH") {
      return { outcome: "already_exited" };
    }
    return { outcome: "failed" };
  }

  const pollInterval = Math.min(200, Math.max(50, Math.floor(graceMs / 20)));
  let waited = 0;
  while (waited < graceMs) {
    await sleepFn(pollInterval);
    waited += pollInterval;
    if (!isAliveFn(pid)) {
      return { outcome: "killed" };
    }
  }

  if (!isAliveFn(pid)) {
    return { outcome: "killed" };
  }

  try {
    killFn(pgid, "SIGKILL");
  } catch (err) {
    if (err && typeof err === "object" && "code" in err && err.code === "ESRCH") {
      return { outcome: "already_exited" };
    }
    return { outcome: "failed" };
  }

  const postKillPollMs =
    opts.postKillPollMs ??
    Number(process.env.FORCED_CANCEL_POST_KILL_POLL_MS || 1000);
  const postInterval = Math.min(200, Math.max(50, Math.floor(postKillPollMs / 10)));
  let postWaited = 0;
  while (postWaited < postKillPollMs) {
    await sleepFn(postInterval);
    postWaited += postInterval;
    if (!isAliveFn(pid)) {
      return { outcome: "killed" };
    }
  }

  return { outcome: isAliveFn(pid) ? "failed" : "killed" };
}
