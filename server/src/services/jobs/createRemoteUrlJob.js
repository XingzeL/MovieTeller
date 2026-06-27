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
import { insertJobDownloading } from "../../db/jobsRepository.js";
import { releaseQuota } from "../billing/releaseQuota.js";
import { reserveQuotaAndInsertDownloadingJob } from "../billing/reserveQuota.js";
import { workflowOptionsFromForm } from "./workflowOptions.js";

function utcNowIso() {
  return new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
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
 * @param {{
 *   userId: string,
 *   sourceUrl: string,
 *   body: Record<string, unknown>,
 *   parsed: { title?: string | null, duration?: number | null, platform?: string | null },
 * }} input
 */
export async function createRemoteUrlJob(input) {
  const userId = String(input.userId || "").trim();
  if (!userId) {
    throw new Error("userId is required to create a job");
  }

  const jobsRoot = getJobsRoot();
  const jobId = crypto.randomUUID();
  const jobRoot = resolveJobRoot(jobsRoot, jobId);
  const paths = jobPathsFromRoot(jobRoot);
  const destVideo = path.join(paths.inputDir, "source.mp4");
  const formOptions = workflowOptionsFromForm(input.body);
  const enableSpeech = formOptions.enableSpeech !== false;
  const sourceDurationSec =
    input.parsed.duration != null && Number(input.parsed.duration) > 0
      ? Number(input.parsed.duration)
      : null;

  let range = null;
  let reservedMinutes = 0;
  let reservedNarrationMinutes = 0;

  if (isDbEnabled()) {
    if (sourceDurationSec) {
      range = await reserveQuotaAndInsertDownloadingJob({
        jobId,
        userId,
        outputRoot: paths.root,
        inputVideoPath: destVideo,
        originalSource: {
          type: "remote_url",
          source_url: input.sourceUrl,
          original_filename: input.parsed.title || null,
          uploaded_at: utcNowIso(),
          platform: input.parsed.platform || null,
        },
        sourceDurationSec,
        enableSpeech,
      });
      reservedMinutes = range.needMinutes;
      reservedNarrationMinutes = range.needNarrationMinutes ?? 0;
    } else {
      await insertJobDownloading({
        jobId,
        userId,
        outputRoot: paths.root,
        inputVideoPath: destVideo,
        originalSource: {
          type: "remote_url",
          source_url: input.sourceUrl,
          original_filename: input.parsed.title || null,
          uploaded_at: utcNowIso(),
          platform: input.parsed.platform || null,
        },
        sourceDurationSec: null,
        processedDurationSec: null,
        reservedMinutes: 0,
        reservedProcessingMinutes: 0,
        reservedNarrationMinutes: 0,
        narrationRequired: enableSpeech,
      });
    }
  }

  try {
    ensureJobDirectories(jobRoot);

    const options = {
      ...formOptions,
      sourceUrl: input.sourceUrl,
    };
    if (input.parsed.title) {
      options.originalFilename = input.parsed.title;
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
    const record = {
      job_id: jobId,
      status: "downloading",
      input_video_path: destVideo,
      output_root: paths.root,
      user_id: userId,
      current_stage: "remote_download",
      progress: { downloadPercent: 0 },
      error: null,
      artifacts: {},
      created_at: now,
      updated_at: now,
      original_source: {
        type: "remote_url",
        source_url: input.sourceUrl,
        original_filename: input.parsed.title || null,
        uploaded_at: now,
        platform: input.parsed.platform || null,
      },
      video_downloaded_at: null,
      video_purged_at: null,
      video_state_version: 0,
      source_duration_sec: sourceDurationSec,
      processed_duration_sec: range?.processedDurationSec ?? null,
      quota_clip_applied: range?.quotaClipApplied ?? false,
      quota_policy: range?.quotaPolicy ?? null,
      reserved_minutes: reservedMinutes,
      reserved_processing_minutes: range?.needProcessingMinutes ?? reservedMinutes,
      reserved_narration_minutes: reservedNarrationMinutes,
      narration_required: enableSpeech,
    };

    fs.writeFileSync(
      paths.workflowJsonPath,
      `${JSON.stringify(record, null, 2)}\n`,
      "utf8"
    );
  } catch (diskErr) {
    if (isDbEnabled() && reservedMinutes > 0) {
      try {
        await releaseQuota(
          userId,
          reservedMinutes,
          range?.reservedUsageDate,
          reservedNarrationMinutes
        );
      } catch (releaseErr) {
        console.error(`[createRemoteUrlJob] releaseQuota failed for ${jobId}`, releaseErr);
      }
      try {
        await deleteJobById(jobId);
      } catch (deleteErr) {
        console.error(`[createRemoteUrlJob] deleteJobById failed for ${jobId}`, deleteErr);
      }
    }
    removeJobRoot(jobRoot);
    throw diskErr;
  }

  return {
    jobId,
    status: "downloading",
    createdAt: utcNowIso(),
    outputRoot: paths.root,
    videoPath: destVideo,
    userId,
    jobsRoot,
    jobRoot,
    sourceUrl: input.sourceUrl,
    sourceDurationSec,
    processedDurationSec: range?.processedDurationSec ?? null,
    quotaClipApplied: range?.quotaClipApplied ?? false,
    quotaClipReasons: range?.quotaPolicy?.clipReasons ?? [],
    primaryClipReason: range?.quotaPolicy?.primaryClipReason ?? null,
  };
}
