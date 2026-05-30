import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";

import {
  getJobsRoot,
  jobPathsFromRoot,
  resolveJobRoot,
} from "../../config/jobs.js";
import { spawnWorkflowJob } from "./spawnWorkflowJob.js";
import { workflowOptionsFromForm } from "./workflowOptions.js";

function utcNowIso() {
  return new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
}

/**
 * 从请求中构建 original_source 信息（更通用的设计）
 * 支持本地上传 + 任意远程链接（YouTube、Bilibili、直接视频 URL 等）
 * @param {any} req
 * @param {string} destVideoPath
 */
function buildOriginalSourceFromRequest(req, destVideoPath) {
  const now = utcNowIso();

  // 远程来源（YouTube、Bilibili、直接视频链接等）
  // 优先尝试常见的远程来源字段名
  const remoteUrl =
    (req.body?.sourceUrl && String(req.body.sourceUrl).trim()) ||
    (req.body?.youtubeUrl && String(req.body.youtubeUrl).trim()) ||
    (req.body?.videoUrl && String(req.body.videoUrl).trim()) ||
    (req.body?.remoteUrl && String(req.body.remoteUrl).trim());

  if (remoteUrl) {
    return {
      type: "remote_url",
      source_url: remoteUrl,
      original_filename: null,
      uploaded_at: now,
    };
  }

  // 本地文件上传
  if (req.file) {
    return {
      type: "local_upload",
      source_url: null,
      original_filename: req.file.originalname || path.basename(destVideoPath),
      uploaded_at: now,
      file_size: req.file.size || null,
      mime_type: req.file.mimetype || null,
    };
  }

  // 兜底
  return {
    type: "unknown",
    source_url: null,
    original_filename: path.basename(destVideoPath),
    uploaded_at: now,
  };
}

/**
 * @param {{ file: { path: string, originalname?: string }, body: Record<string, unknown>, spawn?: boolean }} input
 */
export function createJobFromUpload(input) {
  const jobsRoot = getJobsRoot();
  const jobId = crypto.randomUUID();
  const jobRoot = resolveJobRoot(jobsRoot, jobId);
  const paths = jobPathsFromRoot(jobRoot);

  for (const dir of [
    paths.inputDir,
    paths.logsDir,
    path.join(jobRoot, "subtitles"),
    path.join(jobRoot, "analysis"),
    path.join(jobRoot, "frame_pool"),
    path.join(jobRoot, "narration"),
    path.join(jobRoot, "speech"),
    path.join(jobRoot, "speech", "audio"),
    path.join(jobRoot, "render"),
    path.join(jobRoot, "study_cards"),
    path.join(jobRoot, "artifacts"),
  ]) {
    fs.mkdirSync(dir, { recursive: true });
  }

  const ext = path.extname(input.file.originalname || "") || ".mp4";
  const destVideo = path.join(paths.inputDir, `source${ext}`);
  fs.renameSync(input.file.path, destVideo);

  const options = workflowOptionsFromForm(input.body);
  fs.writeFileSync(
    paths.requestJsonPath,
    `${JSON.stringify(options, null, 2)}\n`,
    "utf8"
  );

  const now = utcNowIso();
  const userId =
    typeof input.body.userId === "string" && input.body.userId.trim()
      ? input.body.userId.trim()
      : null;

  const shouldSpawn = input.spawn !== false;
  const status = shouldSpawn ? "queued" : "queued";

  const originalSource = buildOriginalSourceFromRequest(input, destVideo);

  const queuedRecord = {
    job_id: jobId,
    status,
    input_video_path: destVideo,
    output_root: paths.root,
    user_id: userId,
    current_stage: null,
    progress: {},
    error: null,
    artifacts: {},
    created_at: now,
    updated_at: now,

    // 新增：原始来源 + 视频存储策略相关字段
    original_source: originalSource,
    video_downloaded_at: null,
    video_purged_at: null,
    video_state_version: 0,   // 用于简单乐观并发控制
  };
  fs.writeFileSync(
    paths.workflowJsonPath,
    `${JSON.stringify(queuedRecord, null, 2)}\n`,
    "utf8"
  );

  if (shouldSpawn) {
    spawnWorkflowJob({
      jobsRoot,
      jobId,
      jobRoot,
      videoPath: destVideo,
      userId,
    });
  }

  return {
    jobId,
    status,
    createdAt: now,
    outputRoot: paths.root,
    videoPath: destVideo,
    userId,
    jobsRoot,
    jobRoot,
  };
}

/**
 * @param {{ jobId: string, jobRoot: string, jobsRoot: string, videoPath: string, userId?: string | null }} prepared
 */
export function spawnPreparedJob(prepared) {
  const paths = jobPathsFromRoot(prepared.jobRoot);
  const now = utcNowIso();
  const record = JSON.parse(fs.readFileSync(paths.workflowJsonPath, "utf8"));
  record.status = "queued";
  record.updated_at = now;
  fs.writeFileSync(paths.workflowJsonPath, `${JSON.stringify(record, null, 2)}\n`, "utf8");
  spawnWorkflowJob({
    jobsRoot: prepared.jobsRoot,
    jobId: prepared.jobId,
    jobRoot: prepared.jobRoot,
    videoPath: prepared.videoPath,
    userId: prepared.userId,
  });
}
