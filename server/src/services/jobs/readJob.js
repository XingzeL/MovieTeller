import fs from "fs";
import path from "path";

import {
  getJobsRoot,
  jobPathsFromRoot,
  resolveJobRoot,
} from "../../config/jobs.js";
import { resolveOriginalSourceForDto } from "./jobDisplaySource.js";

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
export function jobRecordToDto(record, request = {}) {
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

    // 新增：用于 Dashboard 历史记录与存储策略
    originalSource: resolveOriginalSourceForDto(record, request),
    videoDownloadedAt: record.video_downloaded_at ?? null,
    videoPurgedAt: record.video_purged_at ?? null,
    videoStateVersion: record.video_state_version ?? 0,

    enableSpeech: request.enableSpeech !== false,
    enableEmbedVideo: request.enableEmbedVideo !== false,
  };
}

/**
 * @param {Record<string, unknown>} record
 * @param {import("./readJobRequest.js").JobRequestMetadata} [request]
 */
export function jobRecordToListItemDto(record, request = {}) {
  const inputPath = String(record.input_video_path || "");
  return {
    jobId: record.job_id,
    status: record.status,
    currentStage: record.current_stage ?? null,
    createdAt: record.created_at,
    updatedAt: record.updated_at,
    cancelRequestedAt: record.cancel_requested_at ?? null,
    inputFileName: inputPath ? path.basename(inputPath) : null,

    // 新增（列表页常用）
    originalSource: resolveOriginalSourceForDto(record, request),
    videoDownloadedAt: record.video_downloaded_at ?? null,
    videoPurgedAt: record.video_purged_at ?? null,
    videoStateVersion: record.video_state_version ?? 0,

    enableSpeech: request.enableSpeech !== false,
    enableEmbedVideo: request.enableEmbedVideo !== false,
  };
}
