import express from "express";
import fs from "fs";
import os from "os";
import path from "path";

import multer from "multer";

import { extractSubtitlesFromVideoFile } from "../services/extraction/runSubtitleExtraction.js";

const upload = multer({
  storage: multer.diskStorage({
    destination: (_req, _file, cb) => cb(null, os.tmpdir()),
    filename: (_req, file, cb) => {
      const base = `${Date.now()}_${Math.random().toString(16).slice(2)}`;
      const ext = path.extname(file.originalname || "") || ".mp4";
      cb(null, `movieteller_${base}${ext}`);
    },
  }),
  limits: { fileSize: 500 * 1024 * 1024 },
});

const router = express.Router();

router.post("/extract/subtitles", upload.single("file"), async (req, res) => {
  if (!req.file?.path) {
    return res.status(400).json({ error: 'multipart field "file" is required' });
  }
  const videoPath = req.file.path;
  const stem = path.basename(videoPath, path.extname(videoPath));
  const outSrt = path.join(path.dirname(videoPath), `${stem}.srt`);

  const cleanup = () => {
    try {
      fs.unlinkSync(videoPath);
    } catch {
      /* ignore */
    }
    try {
      fs.unlinkSync(outSrt);
    } catch {
      /* ignore */
    }
  };

  try {
    const data = await extractSubtitlesFromVideoFile(videoPath, { outputSrtPath: outSrt });
    res.json({
      cues: data.cues,
    });
  } catch (e) {
    console.error(e);
    res.status(500).json({ error: String(e?.message || e) });
  } finally {
    setImmediate(cleanup);
  }
});

export default router;
