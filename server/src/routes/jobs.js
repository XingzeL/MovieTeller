import express from "express";
import multer from "multer";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

import { respondDatabaseError } from "../db/errors.js";
import { respondBillingError } from "../services/billing/errors.js";
import { appendAuditEvent } from "../services/audit/auditLog.js";
import {
  downloadRemoteVideo,
  removeDownloadDir,
} from "../services/media/downloadRemoteVideo.js";
import {
  extractSourceUrlFromBody,
  validateSourceUrl,
} from "../services/media/validateSourceUrl.js";
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

router.get("/jobs", async (req, res) => {
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
    const payload = await listJobsForUser(req.user.id, {
      limit: Number.isNaN(limit) ? undefined : limit,
      offset: Number.isNaN(offset) ? undefined : offset,
    });
    return res.json(payload);
  } catch (err) {
    return respondDatabaseError(res, err);
  }
});

const URL_JOB_CREATE_TIMEOUT_MS = 15 * 60 * 1000;

/**
 * @param {import('express').Request} req
 * @param {import('express').Response} res
 * @param {{ file: import('multer').File, body: Record<string, unknown> }} input
 */
async function createJobFromRequest(req, res, input) {
  const created = await enqueueJobUpload({
    file: input.file,
    body: input.body,
    userId: req.user.id,
  });
  appendAuditEvent({
    jobId: created.jobId,
    userId: req.user.id,
    event: "job.created",
  });
  return res.status(201).json(created);
}

router.post("/jobs", upload.single("file"), async (req, res) => {
  const isMultipart = req.is("multipart/form-data");

  if (isMultipart) {
    if (!req.file?.path) {
      return res.status(400).json({ error: 'multipart field "file" is required' });
    }
    const validation = validateJobUploadFile(req.file);
    if (!validation.ok) {
      removeUploadedTempFile(req.file.path);
      return res.status(400).json({ error: validation.message });
    }
    try {
      return await createJobFromRequest(req, res, {
        file: req.file,
        body: req.body ?? {},
      });
    } catch (err) {
      if (respondBillingError(res, err)) return;
      return respondDatabaseError(res, err);
    }
  }

  if (req.is("application/json")) {
    req.setTimeout(URL_JOB_CREATE_TIMEOUT_MS);
    const sourceUrl = extractSourceUrlFromBody(req.body);
    if (!sourceUrl) {
      return res.status(400).json({ error: "sourceUrl is required" });
    }
    const urlValidation = validateSourceUrl(sourceUrl);
    if (!urlValidation.ok) {
      return res.status(400).json({ error: urlValidation.message });
    }

    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "movieteller_dl_"));
    let downloaded;
    try {
      downloaded = await downloadRemoteVideo(urlValidation.url, tmpDir);
      const fileValidation = validateJobUploadFile({
        path: downloaded.path,
        originalname: downloaded.originalname,
        mimetype: downloaded.mimetype,
        size: downloaded.size,
      });
      if (!fileValidation.ok) {
        removeDownloadDir(tmpDir);
        return res.status(400).json({ error: fileValidation.message });
      }
      const pseudoFile = {
        path: downloaded.path,
        originalname: downloaded.originalname,
        mimetype: downloaded.mimetype,
        size: downloaded.size,
      };
      return await createJobFromRequest(req, res, {
        file: pseudoFile,
        body: { ...(req.body ?? {}), sourceUrl: urlValidation.url },
      });
    } catch (err) {
      removeDownloadDir(tmpDir);
      if (respondBillingError(res, err)) return;
      return respondDatabaseError(res, err);
    }
  }

  return res.status(415).json({
    error: 'use multipart/form-data with "file" or application/json with "sourceUrl"',
  });
});

router.get("/jobs/:jobId", async (req, res) => {
  try {
    const { record, paths } = await readJobForUser(req.user.id, req.params.jobId);
    return res.json({
      job: await jobRecordToDto(
        record,
        readJobRequestMetadata(paths.root),
        paths.root
      ),
    });
  } catch (err) {
    const status = err.statusCode === 404 ? 404 : undefined;
    if (status) {
      return res.status(404).json({ error: String(err?.message || err) });
    }
    return respondDatabaseError(res, err);
  }
});

router.get("/jobs/:jobId/progress", async (req, res) => {
  try {
    const { paths } = await readJobForUser(req.user.id, req.params.jobId);
    const progress = await readWorkflowProgressFromLog(paths.workflowLogPath);
    return res.json({ progress });
  } catch (err) {
    const status = err.statusCode === 404 ? 404 : undefined;
    if (status) {
      return res.status(404).json({ error: String(err?.message || err) });
    }
    return respondDatabaseError(res, err);
  }
});

router.get("/jobs/:jobId/logs", async (req, res) => {
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
    const payload = await readJobLogsForUser(req.user.id, req.params.jobId, {
      limit: Number.isNaN(limit) ? undefined : limit,
      after: Number.isNaN(after) ? undefined : after,
    });
    return res.json(payload);
  } catch (err) {
    const status = err.statusCode === 404 ? 404 : undefined;
    if (status) {
      return res.status(404).json({ error: String(err?.message || err) });
    }
    return respondDatabaseError(res, err);
  }
});

router.get("/jobs/:jobId/artifacts", async (req, res) => {
  try {
    const artifacts = await listArtifactsForUser(req.user.id, req.params.jobId);
    return res.json({ artifacts });
  } catch (err) {
    const status = err.statusCode === 404 ? 404 : undefined;
    if (status) {
      return res.status(404).json({ error: String(err?.message || err) });
    }
    return respondDatabaseError(res, err);
  }
});

router.get("/jobs/:jobId/thumbnail", async (req, res) => {
  try {
    const { filePath } = await resolveThumbnailForUser(
      req.user.id,
      req.params.jobId
    );
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
    const status = err.statusCode === 403 || err.statusCode === 404 ? err.statusCode : undefined;
    if (status) {
      return res.status(status).json({ error: String(err?.message || err) });
    }
    return respondDatabaseError(res, err);
  }
});

router.get("/jobs/:jobId/artifacts/:kind", async (req, res) => {
  try {
    const resolved = await resolveArtifactForUser(
      req.user.id,
      req.params.jobId,
      req.params.kind
    );
    const filePath = "filePath" in resolved ? resolved.filePath : undefined;
    const html = "html" in resolved ? resolved.html : undefined;
    const label = resolved.label || req.params.kind;

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
      if (html) {
        res.type("text/html");
        res.setHeader("Content-Disposition", "inline");
        return res.send(html);
      }
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

    if (html) {
      res.setHeader(
        "Content-Disposition",
        `attachment; filename="${path.basename(label)}"`
      );
      res.type("text/html");
      return res.send(html);
    }

    return res.download(filePath, path.basename(filePath), (err) => {
      if (err) {
        console.error("artifact download failed", label, err);
        return;
      }

      if (isVideoDownload) {
        void markVideoDownloadedForUser(req.user.id, req.params.jobId)
          .then(() => {
            appendAuditEvent({
              jobId: req.params.jobId,
              userId: req.user.id,
              event: "job.video_downloaded",
            });
          })
          .catch((e) => {
            console.error("Failed to mark video_downloaded_at", e);
          });
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
        : undefined;
    if (status) {
      return res.status(status).json({ error: String(err?.message || err) });
    }
    return respondDatabaseError(res, err);
  }
});

router.post("/jobs/:jobId/cancel", async (req, res) => {
  try {
    const payload = await cancelJobForUser(req.user.id, req.params.jobId);
    appendAuditEvent({
      jobId: req.params.jobId,
      userId: req.user.id,
      event: "job.canceled",
      detail: { status: payload.status },
    });
    return res.json(payload);
  } catch (err) {
    const status = err.statusCode === 404 ? 404 : undefined;
    if (status) {
      return res.status(404).json({ error: String(err?.message || err) });
    }
    return respondDatabaseError(res, err);
  }
});

router.post("/jobs/:jobId/retry", async (req, res) => {
  try {
    const payload = await retryJobForUser(req.user.id, req.params.jobId);
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
        : undefined;
    if (status) {
      return res.status(status).json({ error: String(err?.message || err) });
    }
    return respondDatabaseError(res, err);
  }
});

export default router;
