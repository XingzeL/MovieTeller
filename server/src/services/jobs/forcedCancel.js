import {
  isForcedCancelEligible,
  markJobForcedCanceledByWorker,
  recordForcedCancelKillFailed,
} from "../../db/jobsRepository.js";
import { markJobCanceledByNode } from "./jobProcess.js";
import { killProcessGroup, readRunnerPid } from "./runnerControl.js";
import {
  releaseQueueSlotAndClaim,
  unregisterDbJobContext,
} from "./jobQueue.js";
import { releaseClaimIfOwned } from "./claimJob.js";

/** @typedef {import('./runnerControl.js').KillProcessGroupOutcome} KillProcessGroupOutcome */

/**
 * @param {KillProcessGroupOutcome} outcome
 */
export function isForcedCancelKillOutcomeAcceptable(outcome) {
  return outcome === "killed" || outcome === "already_exited" || outcome === "no_pid";
}

/**
 * Force-cancel past deadline: eligibility check → kill → finalize DB/workflow only if kill OK.
 *
 * @param {{
 *   jobId: string,
 *   jobRoot: string,
 *   attemptId: number,
 *   claimedBy: string,
 *   killFn?: (pid: number, signal: NodeJS.Signals) => void,
 *   graceMs?: number,
 * }} input
 * @returns {Promise<boolean>}
 */
export async function applyForcedCancel(input) {
  const { jobId, jobRoot, attemptId, claimedBy } = input;

  const eligible = await isForcedCancelEligible({
    jobId,
    attemptId,
    claimedBy,
  });
  if (!eligible) {
    return false;
  }

  const pid = readRunnerPid(jobRoot);
  /** @type {KillProcessGroupOutcome} */
  let killOutcome = "no_pid";
  if (pid) {
    const result = await killProcessGroup(pid, {
      killFn: input.killFn,
      graceMs: input.graceMs,
    });
    killOutcome = result.outcome;
  }

  if (!isForcedCancelKillOutcomeAcceptable(killOutcome)) {
    await recordForcedCancelKillFailed({
      jobId,
      attemptId,
      claimedBy,
      detail: `kill outcome: ${killOutcome}`,
    });
    return false;
  }

  const finalized = await markJobForcedCanceledByWorker({
    jobId,
    attemptId,
    claimedBy,
  });
  if (!finalized) {
    return false;
  }

  markJobCanceledByNode(jobRoot, { cancelMode: "forced" });

  unregisterDbJobContext(jobId);
  releaseQueueSlotAndClaim(jobId, jobRoot);
  releaseClaimIfOwned(jobRoot);

  return true;
}
