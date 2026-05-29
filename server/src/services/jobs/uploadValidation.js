import fs from "node:fs";
import path from "node:path";

const ALLOWED_EXTENSIONS = new Set([
  ".mp4",
  ".mov",
  ".mkv",
  ".webm",
  ".m4v",
]);

const ALLOWED_MIME_TYPES = new Set([
  "video/mp4",
  "video/quicktime",
  "video/x-matroska",
  "video/webm",
  "video/x-m4v",
  "application/octet-stream",
]);

/**
 * @param {{ path?: string, originalname?: string, mimetype?: string, size?: number }} file
 * @returns {{ ok: true } | { ok: false, message: string }}
 */
export function validateJobUploadFile(file) {
  if (!file?.path) {
    return { ok: false, message: 'multipart field "file" is required' };
  }

  const ext = path.extname(file.originalname || file.path).toLowerCase();
  if (!ALLOWED_EXTENSIONS.has(ext)) {
    return {
      ok: false,
      message: `unsupported video format "${ext || "(none)"}"; allowed: ${[...ALLOWED_EXTENSIONS].join(", ")}`,
    };
  }

  const mime = String(file.mimetype || "").toLowerCase().trim();
  if (mime && !ALLOWED_MIME_TYPES.has(mime)) {
    return {
      ok: false,
      message: `unsupported content type "${mime}"; upload a video file (${[...ALLOWED_EXTENSIONS].join(", ")})`,
    };
  }

  if (typeof file.size === "number" && file.size <= 0) {
    return { ok: false, message: "uploaded file is empty" };
  }

  return { ok: true };
}

/**
 * @param {string} filePath
 */
export function removeUploadedTempFile(filePath) {
  if (!filePath) return;
  try {
    fs.unlinkSync(filePath);
  } catch {
    // ignore missing temp file
  }
}
