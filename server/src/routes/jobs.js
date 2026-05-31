import express from "express";
import multer from "multer";
import os from "node:os";
import path from "node:path";

import { appendAuditEvent } from "../services/audit/auditLog.js";
import {
  listArtifactsForUser,
  cancelJobForUser,
  listJobsForUser,
  markVideoDownloadedForUser,
  readJobForUser,
  readJobLogsForUser,
  resolveArtifactForUser,
  resolveThumbnailForUser,
  retryJobForUser,
} from "../services/jobs/jobAccess.js";
import { enqueueJobUpload } from "../services/jobs/jobQueue.js";
import { readJobRequestMetadata } from "../services/jobs/readJobRequest.js";
import { jobRecordToDto } from "../services/jobs/readJob.js";
import {
  removeUploadedTempFile,
  validateJobUploadFile,
} from "../services/jobs/uploadValidation.js";
import { readWorkflowProgressFromLog } from "../services/workflow/readWorkflowProgress.js";

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
    const payload = listJobsForUser(req.user.id, {
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
      userId: req.user.id,
    });
    appendAuditEvent({
      jobId: created.jobId,
      userId: req.user.id,
      event: "job.created",
    });
    return res.status(201).json(created);
  } catch (err) {
    console.error(err);
    return res.status(500).json({ error: String(err?.message || err) });
  }
});

router.get("/jobs/:jobId", (req, res) => {
  try {
    const { record, paths } = readJobForUser(req.user.id, req.params.jobId);
    return res.json({
      job: jobRecordToDto(
        record,
        readJobRequestMetadata(paths.root),
        paths.root
      ),
    });
  } catch (err) {
    const status = err.statusCode === 404 ? 404 : 500;
    return res.status(status).json({ error: String(err?.message || err) });
  }
});

router.get("/jobs/:jobId/progress", async (req, res) => {
  try {
    const { paths } = readJobForUser(req.user.id, req.params.jobId);
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
    const payload = readJobLogsForUser(req.user.id, req.params.jobId, {
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
    const artifacts = listArtifactsForUser(req.user.id, req.params.jobId);
    return res.json({ artifacts });
  } catch (err) {
    const status = err.statusCode === 404 ? 404 : 500;
    return res.status(status).json({ error: String(err?.message || err) });
  }
});

router.get("/jobs/:jobId/thumbnail", (req, res) => {
  try {
    const { filePath } = resolveThumbnailForUser(req.user.id, req.params.jobId);
    res.type(
      path.extname(filePath).toLowerCase() === ".jpg" ? "image/jpeg" : "image/png"
    );
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
    const { filePath, label } = resolveArtifactForUser(
      req.user.id,
      req.params.jobId,
      req.params.kind
    );

    const wantsInline =
      req.query.inline === "1" || req.query.inline === "true";
    const isVideoDownload = req.params.kind === "renderedVideo";

    if (wantsInline) {
      if (isVideoDownload) {
        return res.status(410).json({ error: "video inline preview is disabled" });
      }
      appendAuditEvent({
        jobId: req.params.jobId,
        userId: req.user.id,
        event: "artifact.access",
        detail: { kind: req.params.kind, inline: true },
      });
      const mime =
        label && label.toLowerCase().endsWith(".html") ? "text/html" : undefined;
      if (mime) res.type(mime);
      res.setHeader("Content-Disposition", "inline");
      return res.sendFile(filePath, (err) => {
        if (err) {
          console.error("artifact inline send failed", label, err);
        }
      });
    }

    return res.download(filePath, path.basename(filePath), (err) => {
      if (err) {
        console.error("artifact download failed", label, err);
        return;
      }

      if (isVideoDownload) {
        try {
          markVideoDownloadedForUser(req.user.id, req.params.jobId);
          appendAuditEvent({
            jobId: req.params.jobId,
            userId: req.user.id,
            event: "job.video_downloaded",
          });
        } catch (e) {
          console.error("Failed to mark video_downloaded_at", e);
        }
      } else {
        appendAuditEvent({
          jobId: req.params.jobId,
          userId: req.user.id,
          event: "artifact.access",
          detail: { kind: req.params.kind, inline: false },
        });
      }
    });
  } catch (err) {
    const status =
      err.statusCode === 404 || err.statusCode === 403 || err.statusCode === 410
        ? err.statusCode
        : 500;
    return res.status(status).json({ error: String(err?.message || err) });
  }
});

router.post("/jobs/:jobId/cancel", (req, res) => {
  try {
    const payload = cancelJobForUser(req.user.id, req.params.jobId);
    appendAuditEvent({
      jobId: req.params.jobId,
      userId: req.user.id,
      event: "job.canceled",
      detail: { status: payload.status },
    });
    return res.json(payload);
  } catch (err) {
    const status = err.statusCode === 404 ? 404 : 500;
    return res.status(status).json({ error: String(err?.message || err) });
  }
});

router.post("/jobs/:jobId/retry", (req, res) => {
  try {
    const payload = retryJobForUser(req.user.id, req.params.jobId);
    appendAuditEvent({
      jobId: req.params.jobId,
      userId: req.user.id,
      event: "job.retried",
    });
    return res.json(payload);
  } catch (err) {
    const status =
      err.statusCode === 404 ||
      err.statusCode === 409 ||
      err.statusCode === 400
        ? err.statusCode
        : 500;
    return res.status(status).json({ error: String(err?.message || err) });
  }
});

export default router;
