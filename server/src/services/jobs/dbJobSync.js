import fs from "node:fs";

import { isDbEnabled } from "../../db/database.js";
import {
  acknowledgeCancel,
  isJobCancelingForWorker,
  reconcileJobFromWorkflow,
  syncVideoStateToDb,
} from "../../db/jobsRepository.js";
import { jobPathsFromRoot } from "../../config/jobs.js";

/**
 * @param {string} jobRoot
 * @param {{ attemptId: number, claimedBy: string }} ctx
 */
export async function syncWorkflowTerminalToDb(jobRoot, ctx) {
  if (!isDbEnabled()) return;
  await reconcileJobFromWorkflow(jobRoot, ctx);
}

/**
 * @param {string} jobId
 * @param {string} jobRoot
 * @param {{ attemptId: number, claimedBy: string }} ctx
 */
export async function ensureCancelFlagForDbJob(jobId, jobRoot, ctx) {
  if (!isDbEnabled()) return;
  const owned = await isJobCancelingForWorker(
    jobId,
    ctx.attemptId,
    ctx.claimedBy
  );
  if (!owned) {
    return;
  }
  const paths = jobPathsFromRoot(jobRoot);
  if (!fs.existsSync(paths.cancelFlagPath)) {
    fs.writeFileSync(paths.cancelFlagPath, `${new Date().toISOString()}\n`, "utf8");
  }
  await acknowledgeCancel(jobId, ctx.attemptId, ctx.claimedBy);
}

/**
 * @param {string} jobId
 * @param {Record<string, unknown>} record
 */
export async function syncVideoFieldsToDb(jobId, record) {
  if (!isDbEnabled()) return;
  await syncVideoStateToDb(jobId, {
    videoDownloadedAt: record.video_downloaded_at ?? undefined,
    videoPurgedAt: record.video_purged_at ?? undefined,
    videoStateVersion: record.video_state_version ?? undefined,
  });
}
