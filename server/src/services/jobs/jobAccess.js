import fs from "node:fs";

import { listJobsForUser as listJobsForUserRecords } from "./listJobs.js";
import { readJobRecord } from "./readJob.js";
import { listJobArtifacts, resolveArtifactDownload } from "./artifactManifest.js";
import { readJobLogs } from "./readJobLogs.js";
import { resolveJobThumbnail } from "./thumbnail.js";
import { cancelJob, requeueExistingJob } from "./jobQueue.js";
import { purgeVideoForJob } from "./purgeVideo.js";

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
export function readJobForUser(userId, jobId) {
  const ctx = readJobRecord(jobId);
  assertJobOwned(userId, ctx.record);
  return ctx;
}

/**
 * @param {string} userId
 * @param {{ limit?: number, offset?: number, jobsRoot?: string }} [opts]
 */
export function listJobsForUser(userId, opts = {}) {
  return listJobsForUserRecords(userId, opts);
}

/**
 * @param {string} userId
 * @param {string} jobId
 * @param {{ limit?: number, after?: number }} [opts]
 */
export function readJobLogsForUser(userId, jobId, opts = {}) {
  readJobForUser(userId, jobId);
  return readJobLogs(jobId, opts);
}

/**
 * @param {string} userId
 * @param {string} jobId
 */
export function listArtifactsForUser(userId, jobId) {
  readJobForUser(userId, jobId);
  return listJobArtifacts(jobId);
}

/**
 * @param {string} userId
 * @param {string} jobId
 * @param {string} kind
 */
export function resolveArtifactForUser(userId, jobId, kind) {
  readJobForUser(userId, jobId);
  return resolveArtifactDownload(jobId, kind);
}

/**
 * @param {string} userId
 * @param {string} jobId
 */
export function resolveThumbnailForUser(userId, jobId) {
  readJobForUser(userId, jobId);
  return resolveJobThumbnail(jobId);
}

/**
 * @param {string} userId
 * @param {string} jobId
 */
export function cancelJobForUser(userId, jobId) {
  readJobForUser(userId, jobId);
  return cancelJob(jobId);
}

/**
 * @param {string} userId
 * @param {string} jobId
 */
export function retryJobForUser(userId, jobId) {
  readJobForUser(userId, jobId);
  return requeueExistingJob(jobId);
}

/**
 * @param {string} userId
 * @param {string} jobId
 */
export function markVideoDownloadedForUser(userId, jobId) {
  const { record, paths } = readJobForUser(userId, jobId);

  if (!record.video_downloaded_at) {
    const previousVersion = record.video_state_version || 0;
    record.video_downloaded_at = new Date().toISOString();
    record.video_state_version = previousVersion + 1;

    fs.writeFileSync(
      paths.workflowJsonPath,
      `${JSON.stringify(record, null, 2)}\n`,
      "utf8"
    );

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
