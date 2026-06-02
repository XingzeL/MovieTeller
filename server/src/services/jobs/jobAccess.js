import fs from "node:fs";

import { isDbEnabled } from "../../db/database.js";
import { listJobsForUser as listJobsForUserRecords } from "./listJobs.js";
import { readJobRecord } from "./readJob.js";
import { listJobArtifacts, resolveArtifactDownload } from "./artifactManifest.js";
import { readJobLogs } from "./readJobLogs.js";
import { resolveJobThumbnail } from "./thumbnail.js";
import { cancelJob, requeueExistingJob } from "./jobQueue.js";
import { purgeVideoForJob } from "./purgeVideo.js";
import { syncVideoFieldsToDb } from "./dbJobSync.js";

/**
 * @param {string} userId
 * @param {Record<string, unknown>} record
 */
export function assertJobOwned(userId, record) {
  const owner = record.user_id;
  if (typeof owner !== "string" || !owner || owner !== userId) {
    const err = new Error("job not found");
    err.statusCode = 404;
    throw err;
  }
}

/**
 * @param {string} userId
 * @param {string} jobId
 */
export async function readJobForUser(userId, jobId) {
  const ctx = await readJobRecord(jobId);
  assertJobOwned(userId, ctx.record);
  return ctx;
}

/**
 * @param {string} userId
 * @param {{ limit?: number, offset?: number, jobsRoot?: string }} [opts]
 */
export async function listJobsForUser(userId, opts = {}) {
  return listJobsForUserRecords(userId, opts);
}

/**
 * @param {string} userId
 * @param {string} jobId
 * @param {{ limit?: number, after?: number }} [opts]
 */
export async function readJobLogsForUser(userId, jobId, opts = {}) {
  await readJobForUser(userId, jobId);
  return readJobLogs(jobId, opts);
}

/**
 * @param {string} userId
 * @param {string} jobId
 */
export async function listArtifactsForUser(userId, jobId) {
  await readJobForUser(userId, jobId);
  return listJobArtifacts(jobId);
}

/**
 * @param {string} userId
 * @param {string} jobId
 * @param {string} kind
 */
export async function resolveArtifactForUser(userId, jobId, kind) {
  const { record } = await readJobForUser(userId, jobId);
  if (
    kind === "renderedVideo" &&
    (record.video_downloaded_at || record.video_purged_at)
  ) {
    const err = new Error("video already downloaded");
    err.statusCode = 410;
    throw err;
  }
  return resolveArtifactDownload(jobId, kind);
}

/**
 * @param {string} userId
 * @param {string} jobId
 */
export async function resolveThumbnailForUser(userId, jobId) {
  await readJobForUser(userId, jobId);
  return resolveJobThumbnail(jobId);
}

/**
 * @param {string} userId
 * @param {string} jobId
 */
export async function cancelJobForUser(userId, jobId) {
  await readJobForUser(userId, jobId);
  return cancelJob(jobId, userId);
}

/**
 * @param {string} userId
 * @param {string} jobId
 */
export async function retryJobForUser(userId, jobId) {
  await readJobForUser(userId, jobId);
  return requeueExistingJob(jobId, userId);
}

/**
 * @param {string} userId
 * @param {string} jobId
 */
export async function markVideoDownloadedForUser(userId, jobId) {
  const { record, paths } = await readJobForUser(userId, jobId);

  if (!record.video_downloaded_at) {
    const previousVersion = record.video_state_version || 0;
    record.video_downloaded_at = new Date().toISOString();
    record.video_state_version = previousVersion + 1;

    fs.writeFileSync(
      paths.workflowJsonPath,
      `${JSON.stringify(record, null, 2)}\n`,
      "utf8"
    );

    await syncVideoFieldsToDb(jobId, record);

    console.log(
      `[Storage] video_downloaded_at marked for job ${jobId} (version ${record.video_state_version})`
    );

    setImmediate(() => {
      try {
        purgeVideoForJob(jobId);
      } catch (purgeErr) {
        console.error(`[Storage] purgeVideoForJob failed for ${jobId}`, purgeErr);
      }
    });
  } else {
    console.log(
      `[Storage] Video download requested again for job ${jobId} (already marked at ${record.video_downloaded_at})`
    );
  }
}
