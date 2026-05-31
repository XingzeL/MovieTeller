import fs from "fs";
import path from "path";

import {
  getJobsRoot,
  jobPathsFromRoot,
  resolveJobRoot,
} from "../../config/jobs.js";
import { resolveOriginalSourceForDto } from "./jobDisplaySource.js";
import { buildJobAvailability } from "./jobAvailability.js";

/**
 * @param {string} jobId
 */
export function readJobRecord(jobId) {
  const jobsRoot = getJobsRoot();
  const jobRoot = resolveJobRoot(jobsRoot, jobId);
  const paths = jobPathsFromRoot(jobRoot);
  if (!fs.existsSync(paths.workflowJsonPath)) {
    const err = new Error("job not found");
    err.statusCode = 404;
    throw err;
  }
  const raw = fs.readFileSync(paths.workflowJsonPath, "utf8");
  const record = JSON.parse(raw);
  return { record, paths, jobsRoot };
}

/**
 * @param {Record<string, unknown>} record
 * @param {import("./readJobRequest.js").JobRequestMetadata} [request]
 */
/**
 * @param {Record<string, unknown>} record
 * @param {import("./readJobRequest.js").JobRequestMetadata} [request]
 * @param {string} [jobRoot]
 */
export function jobRecordToDto(record, request = {}, jobRoot = "") {
  const availability = jobRoot
    ? buildJobAvailability(record, request, jobRoot)
    : {
        videoState: "not_generated",
        canDownloadVideo: false,
        canOpenStudyCards: false,
      };

  return {
    jobId: record.job_id,
    status: record.status,
    currentStage: record.current_stage ?? null,
    progress: record.progress ?? {},
    error: record.error ?? null,
    artifacts: record.artifacts ?? {},
    outputRoot: record.output_root,
    inputVideoPath: record.input_video_path,
    userId: record.user_id ?? null,
    createdAt: record.created_at,
    updatedAt: record.updated_at,
    cancelRequestedAt: record.cancel_requested_at ?? null,

    originalSource: resolveOriginalSourceForDto(record, request),
    videoDownloadedAt: record.video_downloaded_at ?? null,
    videoPurgedAt: record.video_purged_at ?? null,
    videoStateVersion: record.video_state_version ?? 0,

    enableSpeech: request.enableSpeech !== false,
    enableEmbedVideo: request.enableEmbedVideo !== false,

    videoState: availability.videoState,
    canDownloadVideo: availability.canDownloadVideo,
    canOpenStudyCards: availability.canOpenStudyCards,
  };
}

/**
 * @param {Record<string, unknown>} record
 * @param {import("./readJobRequest.js").JobRequestMetadata} [request]
 */
/**
 * @param {Record<string, unknown>} record
 * @param {import("./readJobRequest.js").JobRequestMetadata} [request]
 * @param {string} [jobRoot]
 */
export function jobRecordToListItemDto(record, request = {}, jobRoot = "") {
  const inputPath = String(record.input_video_path || "");
  const availability = jobRoot
    ? buildJobAvailability(record, request, jobRoot)
    : {
        videoState: "not_generated",
        canDownloadVideo: false,
        canOpenStudyCards: false,
      };

  return {
    jobId: record.job_id,
    status: record.status,
    currentStage: record.current_stage ?? null,
    createdAt: record.created_at,
    updatedAt: record.updated_at,
    cancelRequestedAt: record.cancel_requested_at ?? null,
    inputFileName: inputPath ? path.basename(inputPath) : null,
    userId: record.user_id ?? null,

    originalSource: resolveOriginalSourceForDto(record, request),
    videoDownloadedAt: record.video_downloaded_at ?? null,
    videoPurgedAt: record.video_purged_at ?? null,
    videoStateVersion: record.video_state_version ?? 0,

    enableSpeech: request.enableSpeech !== false,
    enableEmbedVideo: request.enableEmbedVideo !== false,

    videoState: availability.videoState,
    canDownloadVideo: availability.canDownloadVideo,
    canOpenStudyCards: availability.canOpenStudyCards,
  };
}
