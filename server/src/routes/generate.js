import express from "express";
import multer from "multer";
import { generateMockNarration, ALLOWED_LEVELS } from "../services/generationService.js";

const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 200 * 1024 * 1024 },
});

const router = express.Router();

function parseLevels(raw) {
  if (raw == null) return null;
  if (Array.isArray(raw)) return raw;
  if (typeof raw === "string") {
    try {
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : null;
    } catch {
      return null;
    }
  }
  return null;
}

function validateLevels(levels) {
  if (!levels || levels.length === 0) return "levels must be a non-empty array";
  const set = new Set(ALLOWED_LEVELS);
  for (const l of levels) {
    if (!set.has(l)) return `invalid level: ${l}`;
  }
  return null;
}

function handleGenerate(req, res) {
  const isMultipart = req.is("multipart/form-data");

  if (isMultipart) {
    const type = req.body?.type;
    if (type !== "file") {
      return res.status(400).json({ error: 'multipart expects type "file" and a file field' });
    }
    if (!req.file) {
      return res.status(400).json({ error: "file is required for type file" });
    }
    const levels = parseLevels(req.body.levels);
    const err = validateLevels(levels);
    if (err) return res.status(400).json({ error: err });
    const inputHint = req.file.originalname || "uploaded.mp4";
    const results = generateMockNarration({ levels, inputHint });
    return res.json({ results });
  }

  const { type, levels: rawLevels, input } = req.body || {};
  if (type !== "url") {
    return res.status(400).json({ error: 'JSON body expects type "url"' });
  }
  const levels = parseLevels(rawLevels);
  const err = validateLevels(levels);
  if (err) return res.status(400).json({ error: err });
  if (!input || typeof input !== "string" || !input.trim()) {
    return res.status(400).json({ error: "input is required for type url" });
  }
  const results = generateMockNarration({ levels, inputHint: input.trim() });
  return res.json({ results });
}

router.post(
  "/generate",
  (req, res, next) => {
    if (req.is("multipart/form-data")) {
      return upload.single("file")(req, res, next);
    }
    return express.json()(req, res, next);
  },
  handleGenerate
);

export default router;
