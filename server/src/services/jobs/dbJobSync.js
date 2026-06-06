import fs from "node:fs";

import { isDbEnabled } from "../../db/database.js";
import {
  acknowledgeCancel,
  isJobCancelingForWorker,
  reconcileJobFromWorkflow,
  syncVideoStateToDb,
} from "../../db/jobsRepository.js";
import { upsertStudyCards } from "../../db/studyCardsRepository.js";
import { finalizeBilling } from "../billing/finalizeBilling.js";
import { jobPathsFromRoot } from "../../config/jobs.js";
import { resolveStudyCardsArtifact } from "./resolveStudyCardsArtifact.js";

/**
 * @param {string} jobRoot
 */
async function syncStudyCardsFromDisk(jobRoot) {
  const paths = jobPathsFromRoot(jobRoot);
  const workflow = JSON.parse(fs.readFileSync(paths.workflowJsonPath, "utf8"));
  const jobId = String(workflow.job_id || "");
  if (!jobId) return;

  const resolved = await resolveStudyCardsArtifact(jobId, jobRoot);
  if (resolved.source !== "disk" || !resolved.path) return;

  const html = fs.readFileSync(resolved.path, "utf8");
  await upsertStudyCards({
    jobId,
    html,
    sourcePath: resolved.path,
  });
}

/**
 * @param {string} jobRoot
 * @param {{ attemptId: number, claimedBy: string }} ctx
 */
export async function syncWorkflowTerminalToDb(jobRoot, ctx) {
  if (!isDbEnabled()) return;
  await reconcileJobFromWorkflow(jobRoot, ctx);

  const paths = jobPathsFromRoot(jobRoot);
  const workflow = readWorkflowRecordSafe(paths.workflowJsonPath);
  const status = String(workflow?.status || "");
  if (["succeeded", "failed", "canceled"].includes(status)) {
    const jobId = String(workflow.job_id || "");
    if (jobId) {
      try {
        await finalizeBilling(jobId);
      } catch (err) {
        console.error(`[dbJobSync] finalizeBilling failed for ${jobId}`, err);
      }
    }
    if (status === "succeeded") {
      try {
        await syncStudyCardsFromDisk(jobRoot);
      } catch (err) {
        console.error(`[dbJobSync] study cards sync failed`, err);
      }
    }
  }
}

/**
 * @param {string} workflowJsonPath
 */
function readWorkflowRecordSafe(workflowJsonPath) {
  if (!fs.existsSync(workflowJsonPath)) return null;
  try {
    return JSON.parse(fs.readFileSync(workflowJsonPath, "utf8"));
  } catch {
    return null;
  }
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
