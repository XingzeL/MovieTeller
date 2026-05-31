import express from "express";
import fs from "node:fs";
import multer from "multer";
import os from "node:os";
import path from "node:path";

import { listJobArtifacts, resolveArtifactDownload } from "../services/jobs/artifactManifest.js";
import { enqueueJobUpload, cancelJob } from "../services/jobs/jobQueue.js";
import { retryJob } from "../services/jobs/retryJob.js";
import { listJobs } from "../services/jobs/listJobs.js";
import { readJobLogs } from "../services/jobs/readJobLogs.js";
import { readJobRequestMetadata } from "../services/jobs/readJobRequest.js";
import { jobRecordToDto, readJobRecord } from "../services/jobs/readJob.js";
import { purgeVideoForJob } from "../services/jobs/purgeVideo.js";
import { resolveJobThumbnail } from "../services/jobs/thumbnail.js";
import {
  removeUploadedTempFile,
  validateJobUploadFile,
} from "../services/jobs/uploadValidation.js";
import {
  readWorkflowProgressFromLog,
} from "../services/workflow/readWorkflowProgress.js";

const upload = multer({
  storage: multer.diskStorage({
    destination: (_req, _file, cb) => cb(null, os.tmpdir()),
    filename: (_req, file, cb) => {
      const base = `${Date.now()}_${Math.random().toString(16).slice(2)}`;
      const ext = path.extname(file.originalname || "") || ".mp4";
      cb(null, `movieteller_job_${base}${ext}`);
    },
  }),
  limits: { fileSize: 500 * 1024 * 1024 },
});

const router = express.Router();

router.get("/jobs", (req, res) => {
  try {
    const limitRaw = req.query.limit;
    const offsetRaw = req.query.offset;
    const limit =
      limitRaw !== undefined && String(limitRaw).trim() !== ""
        ? Number(limitRaw)
        : undefined;
    const offset =
      offsetRaw !== undefined && String(offsetRaw).trim() !== ""
        ? Number(offsetRaw)
        : undefined;
    const payload = listJobs({
      limit: Number.isNaN(limit) ? undefined : limit,
      offset: Number.isNaN(offset) ? undefined : offset,
    });
    return res.json(payload);
  } catch (err) {
    console.error(err);
    return res.status(500).json({ error: String(err?.message || err) });
  }
});

router.post("/jobs", upload.single("file"), (req, res) => {
  if (!req.file?.path) {
    return res.status(400).json({ error: 'multipart field "file" is required' });
  }
  const validation = validateJobUploadFile(req.file);
  if (!validation.ok) {
    removeUploadedTempFile(req.file.path);
    return res.status(400).json({ error: validation.message });
  }
  try {
    const created = enqueueJobUpload({
      file: req.file,
      body: req.body ?? {},
    });
    return res.status(201).json(created);
  } catch (err) {
    console.error(err);
    return res.status(500).json({ error: String(err?.message || err) });
  }
});

router.get("/jobs/:jobId", (req, res) => {
  try {
    const { record, paths } = readJobRecord(req.params.jobId);
    return res.json({
      job: jobRecordToDto(record, readJobRequestMetadata(paths.root)),
    });
  } catch (err) {
    const status = err.statusCode === 404 ? 404 : 500;
    return res.status(status).json({ error: String(err?.message || err) });
  }
});

router.get("/jobs/:jobId/progress", async (req, res) => {
  try {
    const { paths } = readJobRecord(req.params.jobId);
    const progress = await readWorkflowProgressFromLog(paths.workflowLogPath);
    return res.json({ progress });
  } catch (err) {
    const status = err.statusCode === 404 ? 404 : 500;
    return res.status(status).json({ error: String(err?.message || err) });
  }
});

router.get("/jobs/:jobId/logs", (req, res) => {
  try {
    const limitRaw = req.query.limit;
    const limit =
      limitRaw !== undefined && String(limitRaw).trim() !== ""
        ? Number(limitRaw)
        : undefined;
    const afterRaw = req.query.after;
    const after =
      afterRaw !== undefined && String(afterRaw).trim() !== ""
        ? Number(afterRaw)
        : undefined;
    const payload = readJobLogs(req.params.jobId, {
      limit: Number.isNaN(limit) ? undefined : limit,
      after: Number.isNaN(after) ? undefined : after,
    });
    return res.json(payload);
  } catch (err) {
    const status = err.statusCode === 404 ? 404 : 500;
    return res.status(status).json({ error: String(err?.message || err) });
  }
});

router.get("/jobs/:jobId/artifacts", (req, res) => {
  try {
    const artifacts = listJobArtifacts(req.params.jobId);
    return res.json({ artifacts });
  } catch (err) {
    const status = err.statusCode === 404 ? 404 : 500;
    return res.status(status).json({ error: String(err?.message || err) });
  }
});

router.get("/jobs/:jobId/thumbnail", (req, res) => {
  try {
    const { filePath } = resolveJobThumbnail(req.params.jobId);
    res.type(path.extname(filePath).toLowerCase() === ".jpg" ? "image/jpeg" : "image/png");
    res.setHeader("Cache-Control", "private, max-age=300");
    return res.sendFile(filePath, (err) => {
      if (err) {
        console.error("thumbnail send failed", req.params.jobId, err);
      }
    });
  } catch (err) {
    const status = err.statusCode === 403 || err.statusCode === 404 ? err.statusCode : 500;
    return res.status(status).json({ error: String(err?.message || err) });
  }
});

router.get("/jobs/:jobId/artifacts/:kind", (req, res) => {
  try {
    const { filePath, label } = resolveArtifactDownload(
      req.params.jobId,
      req.params.kind
    );

    const wantsInline = req.query.inline === '1' || req.query.inline === 'true';

    if (wantsInline) {
      // For preview in <iframe> or <video> — serve content inline without forcing download
      const mime = label && label.toLowerCase().endsWith('.html') ? 'text/html' : undefined;
      if (mime) res.type(mime);
      res.setHeader('Content-Disposition', 'inline');
      return res.sendFile(filePath, (err) => {
        if (err) {
          console.error("artifact inline send failed", label, err);
        }
      });
    }

    // Default behavior: force download (used by the "下载完整..." buttons)
    const isVideoDownload = req.params.kind === "renderedVideo";

    return res.download(filePath, path.basename(filePath), (err) => {
      if (err) {
        console.error("artifact download failed", label, err);
        return;
      }

      // === 加强版存储策略：视频下载后打标 + 异步清理 ===
      if (isVideoDownload) {
        try {
          const { record, paths } = readJobRecord(req.params.jobId);

          // 简单乐观并发保护：只有在还没被标记时才写入
          if (!record.video_downloaded_at) {
            const previousVersion = record.video_state_version || 0;

            record.video_downloaded_at = new Date().toISOString();
            record.video_state_version = previousVersion + 1;

            fs.writeFileSync(paths.workflowJsonPath, `${JSON.stringify(record, null, 2)}\n`, "utf8");

            console.log(`[Storage] video_downloaded_at marked for job ${req.params.jobId} (version ${record.video_state_version})`);

            // 异步触发清理（不阻塞下载响应）
            setImmediate(() => {
              try {
                purgeVideoForJob(req.params.jobId);
              } catch (purgeErr) {
                console.error(`[Storage] purgeVideoForJob failed for ${req.params.jobId}`, purgeErr);
              }
            });
          } else {
            console.log(`[Storage] Video download requested again for job ${req.params.jobId} (already marked at ${record.video_downloaded_at})`);
          }
        } catch (e) {
          console.error("Failed to mark video_downloaded_at", e);
        }
      }
    });
  } catch (err) {
    const status = err.statusCode === 404 || err.statusCode === 403 ? err.statusCode : 500;
    return res.status(status).json({ error: String(err?.message || err) });
  }
});

router.post("/jobs/:jobId/cancel", (req, res) => {
  try {
    const payload = cancelJob(req.params.jobId);
    return res.json(payload);
  } catch (err) {
    return res.status(500).json({ error: String(err?.message || err) });
  }
});

router.post("/jobs/:jobId/retry", (req, res) => {
  try {
    const payload = retryJob(req.params.jobId);
    return res.json(payload);
  } catch (err) {
    const status = err.statusCode === 404 || err.statusCode === 409 || err.statusCode === 400
      ? err.statusCode
      : 500;
    return res.status(status).json({ error: String(err?.message || err) });
  }
});

export default router;
