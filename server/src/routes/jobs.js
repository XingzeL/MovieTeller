import express from "express";
import multer from "multer";
import os from "node:os";
import path from "node:path";

import { listJobArtifacts, resolveArtifactDownload } from "../services/jobs/artifactManifest.js";
import { enqueueJobUpload, cancelJob } from "../services/jobs/jobQueue.js";
import { readJobLogs } from "../services/jobs/readJobLogs.js";
import { jobRecordToDto, readJobRecord } from "../services/jobs/readJob.js";
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

router.post("/jobs", upload.single("file"), (req, res) => {
  if (!req.file?.path) {
    return res.status(400).json({ error: 'multipart field "file" is required' });
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
    const { record } = readJobRecord(req.params.jobId);
    return res.json({ job: jobRecordToDto(record) });
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

router.get("/jobs/:jobId/artifacts/:kind", (req, res) => {
  try {
    const { filePath, label } = resolveArtifactDownload(
      req.params.jobId,
      req.params.kind
    );
    return res.download(filePath, path.basename(filePath), (err) => {
      if (err) {
        console.error("artifact download failed", label, err);
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

export default router;
