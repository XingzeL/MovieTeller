import fs from "node:fs";
import os from "node:os";
import path from "node:path";

import { getJobsRoot, jobPathsFromRoot, resolveJobRoot } from "../../config/jobs.js";
import { isDbEnabled } from "../../db/database.js";
import {
  claimNextDownloadingJob,
  failDownloadingJob,
  getJobById,
  markJobCanceledDownloading,
  markJobQueuedAfterDownload,
  requestCancelDownloadingJob,
} from "../../db/jobsRepository.js";
import { isApiRunMode, isWorkerRunMode } from "../../runtime/runMode.js";
import { finalizeBilling } from "../billing/finalizeBilling.js";
import { PlanQuotaExhaustedError } from "../billing/errors.js";
import { releaseQuota } from "../billing/releaseQuota.js";
import { reserveQuotaForProbedDownloadingJob } from "../billing/reserveQuota.js";
import {
  downloadRemoteVideo,
  removeDownloadDir,
} from "../media/downloadRemoteVideo.js";
import { probeDurationSec } from "../media/probeDuration.js";
import { summarizeYtDlpFailure } from "../media/ytDlpOptions.js";
import { enqueuePreparedJob } from "./jobQueue.js";
import { readWorkflowRecord } from "./jobProcess.js";
import { validateJobUploadFile } from "./uploadValidation.js";
import { getWorkerId } from "./workerId.js";
import { scanAllJobsForSystem } from "./scanAllJobsForSystem.js";

/** @type {Map<string, { child?: { kill: (signal?: string) => void }, tmpDir?: string, jobRoot: string }>} */
const activeDownloads = new Map();

/** @type {ReturnType<typeof setInterval> | null} */
let downloadLoop = null;

function utcNowIso() {
  return new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
}

/**
 * @param {string} jobId
 */
export function killActiveRemoteDownload(jobId) {
  const ctx = activeDownloads.get(jobId);
  if (!ctx) return false;
  try {
    ctx.child?.kill("SIGKILL");
  } catch {
    /* ignore */
  }
  if (ctx.tmpDir) {
    removeDownloadDir(ctx.tmpDir);
  }
  activeDownloads.delete(jobId);
  return true;
}

/**
 * @param {string} jobRoot
 */
function readSourceUrl(jobRoot) {
  const paths = jobPathsFromRoot(jobRoot);
  const record = readWorkflowRecord(paths.workflowJsonPath);
  const fromWorkflow = record?.original_source?.source_url;
  if (fromWorkflow) return String(fromWorkflow);
  if (fs.existsSync(paths.requestJsonPath)) {
    const req = JSON.parse(fs.readFileSync(paths.requestJsonPath, "utf8"));
    if (req?.sourceUrl) return String(req.sourceUrl);
  }
  return null;
}

/**
 * @param {string} jobRoot
 * @param {string} destVideo
 * @param {{ sourceDurationSec?: number | null, processedDurationSec?: number | null, range?: { startPoint?: number, endPoint?: number } | null }} [meta]
 */
function markWorkflowQueued(jobRoot, destVideo, meta = {}) {
  const paths = jobPathsFromRoot(jobRoot);
  const record = readWorkflowRecord(paths.workflowJsonPath);
  if (!record) return;
  record.status = "queued";
  record.current_stage = null;
  record.progress = {};
  record.input_video_path = destVideo;
  if (meta.sourceDurationSec != null && meta.sourceDurationSec > 0) {
    record.source_duration_sec = meta.sourceDurationSec;
  }
  if (meta.processedDurationSec != null && meta.processedDurationSec > 0) {
    record.processed_duration_sec = meta.processedDurationSec;
  }
  record.updated_at = utcNowIso();
  fs.writeFileSync(
    paths.workflowJsonPath,
    `${JSON.stringify(record, null, 2)}\n`,
    "utf8"
  );

  if (
    meta.range &&
    (meta.range.startPoint != null || meta.range.endPoint != null) &&
    fs.existsSync(paths.requestJsonPath)
  ) {
    try {
      const req = JSON.parse(fs.readFileSync(paths.requestJsonPath, "utf8"));
      if (meta.range.startPoint != null) req.startPoint = meta.range.startPoint;
      if (meta.range.endPoint != null) req.endPoint = meta.range.endPoint;
      fs.writeFileSync(
        paths.requestJsonPath,
        `${JSON.stringify(req, null, 2)}\n`,
        "utf8"
      );
    } catch {
      /* ignore */
    }
  }
}

/**
 * @param {string} jobRoot
 * @param {{ errorCode: string, errorMessage: string }} err
 */
function markWorkflowDownloadFailed(jobRoot, err) {
  const paths = jobPathsFromRoot(jobRoot);
  const record = readWorkflowRecord(paths.workflowJsonPath);
  if (!record) return;
  record.status = "failed";
  record.error = {
    code: err.errorCode,
    message: err.errorMessage,
    retryable: true,
  };
  record.updated_at = utcNowIso();
  fs.writeFileSync(
    paths.workflowJsonPath,
    `${JSON.stringify(record, null, 2)}\n`,
    "utf8"
  );
}

/**
 * @param {unknown[]} values
 */
function firstPositiveDurationSec(...values) {
  for (const value of values) {
    const duration = Number(value);
    if (Number.isFinite(duration) && duration > 0) {
      return Math.ceil(duration);
    }
  }
  return null;
}

/**
 * @param {{ jobId: string, jobRoot: string, sourceUrl: string, destVideo: string, userId?: string | null }} job
 */
async function executeRemoteDownload(job) {
  if (activeDownloads.has(job.jobId)) return;

  const paths = jobPathsFromRoot(job.jobRoot);
  if (fs.existsSync(paths.cancelFlagPath)) {
    return;
  }

  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "movieteller_dl_"));
  activeDownloads.set(job.jobId, { jobRoot: job.jobRoot, tmpDir });

  try {
    const downloaded = await downloadRemoteVideo(job.sourceUrl, tmpDir, {
      onSpawn: (child) => {
        const ctx = activeDownloads.get(job.jobId);
        if (ctx) ctx.child = child;
      },
    });

    if (fs.existsSync(paths.cancelFlagPath)) {
      removeDownloadDir(tmpDir);
      return;
    }

    const fileValidation = validateJobUploadFile({
      path: downloaded.path,
      originalname: downloaded.originalname,
      mimetype: downloaded.mimetype,
      size: downloaded.size,
    });
    if (!fileValidation.ok) {
      throw new Error(fileValidation.message);
    }

    fs.mkdirSync(path.dirname(job.destVideo), { recursive: true });
    fs.renameSync(downloaded.path, job.destVideo);
    removeDownloadDir(tmpDir);

    let dbJob = null;
    if (isDbEnabled() && job.userId) {
      dbJob = await getJobById(job.jobId);
    }

    const metadataDurationSec = firstPositiveDurationSec(
      downloaded.durationSec,
      dbJob?.source_duration_sec
    );
    let durationSec;
    try {
      durationSec = await probeDurationSec(job.destVideo);
    } catch (probeErr) {
      if (!metadataDurationSec) {
        throw probeErr;
      }
      console.warn(
        `[remoteDownloadWorker] ffprobe failed for ${job.jobId}; using parsed duration ${metadataDurationSec}s:`,
        probeErr instanceof Error ? probeErr.message : probeErr
      );
      durationSec = metadataDurationSec;
    }

    let quotaRange = null;
    if (isDbEnabled() && job.userId) {
      const needsDeferredQuota =
        !dbJob?.source_duration_sec || Number(dbJob.reserved_minutes) === 0;
      if (needsDeferredQuota) {
        const enableSpeech = dbJob?.narration_required !== false;
        try {
          quotaRange = await reserveQuotaForProbedDownloadingJob({
            jobId: job.jobId,
            userId: job.userId,
            sourceDurationSec: durationSec,
            enableSpeech,
          });
        } catch (quotaErr) {
          try {
            fs.unlinkSync(job.destVideo);
          } catch {
            /* ignore */
          }
          if (quotaErr instanceof PlanQuotaExhaustedError) {
            markWorkflowDownloadFailed(job.jobRoot, {
              errorCode: quotaErr.code,
              errorMessage: quotaErr.message,
            });
            await failDownloadingJob(job.jobId, quotaErr.code, quotaErr.message);
            await finalizeBilling(job.jobId);
            return;
          }
          throw quotaErr;
        }
      }
    }

    markWorkflowQueued(job.jobRoot, job.destVideo, {
      sourceDurationSec: durationSec,
      processedDurationSec:
        quotaRange?.processedDurationSec ?? durationSec,
      range:
        quotaRange?.startPoint != null || quotaRange?.endPoint != null
          ? { startPoint: quotaRange.startPoint, endPoint: quotaRange.endPoint }
          : null,
    });
    if (isDbEnabled()) {
      await markJobQueuedAfterDownload(job.jobId);
    }

    const maySpawnInline = !isApiRunMode() && !isWorkerRunMode();
    if (maySpawnInline) {
      enqueuePreparedJob({
        jobId: job.jobId,
        jobRoot: job.jobRoot,
        jobsRoot: getJobsRoot(),
        videoPath: job.destVideo,
        userId: job.userId ?? null,
      });
    }
  } catch (err) {
    removeDownloadDir(tmpDir);
    const message = err instanceof Error ? err.message : String(err);
    const publicMessage = summarizeYtDlpFailure(message);
    console.error(`[remoteDownloadWorker] remote download failed for ${job.jobId}:`, message);
    markWorkflowDownloadFailed(job.jobRoot, {
      errorCode: "video_download_failed",
      errorMessage: publicMessage,
    });
    if (isDbEnabled()) {
      await failDownloadingJob(job.jobId, "video_download_failed", publicMessage);
      await finalizeBilling(job.jobId);
    }
  } finally {
    activeDownloads.delete(job.jobId);
  }
}

/**
 * @param {{ jobsRoot?: string }} [opts]
 */
export async function tickRemoteDownloadsOnce(opts = {}) {
  const jobsRoot = opts.jobsRoot || getJobsRoot();

  if (isDbEnabled()) {
    if (activeDownloads.size > 0) {
      for (const jobId of activeDownloads.keys()) {
        const row = await getJobById(jobId);
        if (row?.cancel_requested_at) {
          killActiveRemoteDownload(jobId);
        }
      }
      return { picked: 0 };
    }

    const claimed = await claimNextDownloadingJob(getWorkerId());
    if (!claimed) return { picked: 0 };

    const jobId = String(claimed.job_id);
    const jobRoot = String(claimed.output_root);
    const sourceUrl = readSourceUrl(jobRoot);
    const destVideo = String(claimed.input_video_path || "");
    if (!sourceUrl || !destVideo) {
      await failDownloadingJob(jobId, "remote_download_prepare_failed", "Missing source URL");
      await finalizeBilling(jobId);
      return { picked: 0 };
    }

    void executeRemoteDownload({
      jobId,
      jobRoot,
      sourceUrl,
      destVideo,
      userId: claimed.user_id ?? null,
    });
    return { picked: 1 };
  }

  if (activeDownloads.size > 0) return { picked: 0 };

  const candidates = (await scanAllJobsForSystem({ jobsRoot }))
    .filter((job) => String(job.record.status || "") === "downloading")
    .filter((job) => {
      const paths = jobPathsFromRoot(job.jobRoot);
      return !fs.existsSync(paths.cancelFlagPath);
    })
    .sort((a, b) => {
      const ca = Date.parse(String(a.record.created_at || "")) || 0;
      const cb = Date.parse(String(b.record.created_at || "")) || 0;
      return ca - cb;
    });

  const next = candidates[0];
  if (!next) return { picked: 0 };

  const sourceUrl = readSourceUrl(next.jobRoot);
  const destVideo = String(next.record.input_video_path || "");
  if (!sourceUrl || !destVideo) return { picked: 0 };

  void executeRemoteDownload({
    jobId: next.jobId,
    jobRoot: next.jobRoot,
    sourceUrl,
    destVideo,
    userId: next.record.user_id ?? null,
  });
  return { picked: 1 };
}

/**
 * @param {{ pollMs?: number }} [opts]
 */
export function startRemoteDownloadLoop(opts = {}) {
  const pollMs = opts.pollMs ?? 2000;
  if (downloadLoop) clearInterval(downloadLoop);
  downloadLoop = setInterval(() => {
    tickRemoteDownloadsOnce().catch((err) => {
      console.error("[remoteDownloadWorker] tick failed", err);
    });
  }, pollMs);
  tickRemoteDownloadsOnce().catch((err) => {
    console.error("[remoteDownloadWorker] initial tick failed", err);
  });
  return { pollMs };
}

/**
 * @param {string} userId
 * @param {string} jobId
 */
export async function cancelRemoteDownloadJob(userId, jobId) {
  const jobsRoot = getJobsRoot();
  const jobRoot = resolveJobRoot(jobsRoot, jobId);
  const paths = jobPathsFromRoot(jobRoot);
  const record = readWorkflowRecord(paths.workflowJsonPath);

  if (isDbEnabled() && userId) {
    await requestCancelDownloadingJob(userId, jobId);
  }

  fs.writeFileSync(paths.cancelFlagPath, `${utcNowIso()}\n`, "utf8");
  killActiveRemoteDownload(jobId);

  if (record && String(record.status) === "downloading") {
    record.status = "canceled";
    record.updated_at = utcNowIso();
    fs.writeFileSync(
      paths.workflowJsonPath,
      `${JSON.stringify(record, null, 2)}\n`,
      "utf8"
    );
    if (isDbEnabled() && userId) {
      await markJobCanceledDownloading(userId, jobId);
      const reservedMinutes = Number(record.reserved_minutes) || 0;
      const reservedNarrationMinutes =
        Number(record.reserved_narration_minutes) || 0;
      if (reservedMinutes > 0 || reservedNarrationMinutes > 0) {
        await releaseQuota(
          userId,
          reservedMinutes,
          record.reserved_usage_date,
          reservedNarrationMinutes
        );
      }
      await finalizeBilling(jobId);
    }
  }

  return { jobId, status: "canceled" };
}

export function clearRemoteDownloadStateForTests() {
  for (const jobId of activeDownloads.keys()) {
    killActiveRemoteDownload(jobId);
  }
  if (downloadLoop) {
    clearInterval(downloadLoop);
    downloadLoop = null;
  }
}
