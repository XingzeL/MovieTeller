import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";

import {
  getJobsRoot,
  jobPathsFromRoot,
  resolveJobRoot,
} from "../../config/jobs.js";
import { isDbEnabled } from "../../db/database.js";
import { deleteJobById } from "../../db/jobsRepository.js";
import { isApiRunMode, isWorkerRunMode } from "../../runtime/runMode.js";
import { releaseQuota } from "../billing/releaseQuota.js";
import { reserveQuotaAndInsertJob } from "../billing/reserveQuota.js";
import { probeDurationSec } from "../media/probeDuration.js";
import { spawnWorkflowJob } from "./spawnWorkflowJob.js";
import { workflowOptionsFromForm } from "./workflowOptions.js";

function utcNowIso() {
  return new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
}

/**
 * @param {any} req
 * @param {string} destVideoPath
 */
function buildOriginalSourceFromRequest(req, destVideoPath) {
  const now = utcNowIso();

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

  return {
    type: "unknown",
    source_url: null,
    original_filename: path.basename(destVideoPath),
    uploaded_at: now,
  };
}

const JOB_SUBDIRS = [
  "input",
  "logs",
  "subtitles",
  "analysis",
  "frame_pool",
  "narration",
  "speech",
  "speech/audio",
  "render",
  "study_cards",
  "artifacts",
];

/**
 * @param {string} jobRoot
 */
function ensureJobDirectories(jobRoot) {
  for (const sub of JOB_SUBDIRS) {
    fs.mkdirSync(path.join(jobRoot, sub), { recursive: true });
  }
}

/**
 * @param {string} jobRoot
 */
function removeJobRoot(jobRoot) {
  if (fs.existsSync(jobRoot)) {
    fs.rmSync(jobRoot, { recursive: true, force: true });
  }
}

/**
 * @param {{ file: { path: string, originalname?: string }, body: Record<string, unknown>, userId: string, spawn?: boolean }} input
 */
export async function createJobFromUpload(input) {
  const userId =
    typeof input.userId === "string" && input.userId.trim()
      ? input.userId.trim()
      : null;
  if (!userId) {
    throw new Error("userId is required to create a job");
  }

  const jobsRoot = getJobsRoot();
  const jobId = crypto.randomUUID();
  const jobRoot = resolveJobRoot(jobsRoot, jobId);
  const paths = jobPathsFromRoot(jobRoot);
  const ext = path.extname(input.file.originalname || "") || ".mp4";
  const destVideo = path.join(paths.inputDir, `source${ext}`);

  let sourceDurationSec = null;
  let range = null;
  let reservedMinutes = 0;
  const shouldSpawn = input.spawn !== false;

  if (isDbEnabled()) {
    try {
      sourceDurationSec = await probeDurationSec(input.file.path);
    } catch (probeErr) {
      if (fs.existsSync(input.file.path)) {
        try {
          fs.unlinkSync(input.file.path);
        } catch {
          /* ignore */
        }
      }
      throw probeErr;
    }

    range = await reserveQuotaAndInsertJob({
      jobId,
      userId,
      outputRoot: paths.root,
      inputVideoPath: destVideo,
      originalSource: buildOriginalSourceFromRequest(input, destVideo),
      sourceDurationSec,
    });
    reservedMinutes = range.needMinutes;
  }

  try {
    ensureJobDirectories(jobRoot);
    fs.renameSync(input.file.path, destVideo);

    const originalSource = buildOriginalSourceFromRequest(input, destVideo);
    const options = workflowOptionsFromForm(input.body);
    if (originalSource.original_filename) {
      options.originalFilename = originalSource.original_filename;
    }
    if (originalSource.source_url) {
      options.sourceUrl = originalSource.source_url;
    }
    if (range) {
      options.startPoint = range.startPoint;
      options.endPoint = range.endPoint;
    }

    fs.writeFileSync(
      paths.requestJsonPath,
      `${JSON.stringify(options, null, 2)}\n`,
      "utf8"
    );

    const now = utcNowIso();
    const status = "queued";

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
      original_source: originalSource,
      video_downloaded_at: null,
      video_purged_at: null,
      video_state_version: 0,
      source_duration_sec: sourceDurationSec,
      processed_duration_sec: range?.processedDurationSec ?? null,
      quota_clip_applied: range?.quotaClipApplied ?? false,
      quota_policy: range?.quotaPolicy ?? null,
      reserved_minutes: reservedMinutes,
    };

    fs.writeFileSync(
      paths.workflowJsonPath,
      `${JSON.stringify(queuedRecord, null, 2)}\n`,
      "utf8"
    );

  } catch (diskErr) {
    if (isDbEnabled() && reservedMinutes > 0) {
      try {
        await releaseQuota(userId, reservedMinutes, range?.reservedUsageDate);
      } catch (releaseErr) {
        console.error(`[createJob] releaseQuota failed for ${jobId}`, releaseErr);
      }
      try {
        await deleteJobById(jobId);
      } catch (deleteErr) {
        console.error(`[createJob] deleteJobById failed for ${jobId}`, deleteErr);
      }
    }
    removeJobRoot(jobRoot);
    if (fs.existsSync(input.file.path)) {
      try {
        fs.unlinkSync(input.file.path);
      } catch {
        /* ignore */
      }
    }
    throw diskErr;
  }

  const maySpawnInline =
    shouldSpawn && !isApiRunMode() && !isWorkerRunMode();
  if (maySpawnInline) {
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
    status: "queued",
    createdAt: utcNowIso(),
    outputRoot: paths.root,
    videoPath: destVideo,
    userId,
    jobsRoot,
    jobRoot,
    sourceDurationSec,
    processedDurationSec: range?.processedDurationSec ?? null,
    quotaClipApplied: range?.quotaClipApplied ?? false,
  };
}

/**
 * @param {{ jobId: string, jobRoot: string, jobsRoot: string, videoPath: string, userId?: string | null }} prepared
 */
export function spawnPreparedJob(prepared) {
  if (isApiRunMode()) {
    throw new Error("spawn is disabled in api run mode");
  }
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
