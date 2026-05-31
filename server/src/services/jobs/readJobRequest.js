import fs from "node:fs";
import path from "node:path";

import { jobPathsFromRoot } from "../../config/jobs.js";

/**
 * @typedef {{
 *   enableSpeech: boolean,
 *   enableEmbedVideo: boolean,
 *   originalFilename: string | null,
 *   sourceUrl: string | null,
 * }} JobRequestMetadata
 */

/**
 * Read per-job workflow flags written at create time (`request.json`).
 * Missing file defaults to speech on for older jobs.
 *
 * @param {string} jobRoot
 * @returns {JobRequestMetadata}
 */
export function readJobRequestMetadata(jobRoot) {
  const requestPath = jobPathsFromRoot(jobRoot).requestJsonPath;
  if (!fs.existsSync(requestPath)) {
    return {
      enableSpeech: true,
      enableEmbedVideo: true,
      originalFilename: null,
      sourceUrl: null,
    };
  }
  try {
    const raw = JSON.parse(fs.readFileSync(requestPath, "utf8"));
    const originalFilename =
      typeof raw.originalFilename === "string" && raw.originalFilename.trim()
        ? raw.originalFilename.trim()
        : null;
    const sourceUrl =
      typeof raw.sourceUrl === "string" && raw.sourceUrl.trim()
        ? raw.sourceUrl.trim()
        : null;
    return {
      enableSpeech: raw.enableSpeech !== false,
      enableEmbedVideo: raw.enableEmbedVideo !== false,
      originalFilename,
      sourceUrl,
    };
  } catch {
    return {
      enableSpeech: true,
      enableEmbedVideo: true,
      originalFilename: null,
      sourceUrl: null,
    };
  }
}

/** @param {string} jobRoot */
export function readJobRequestOptions(jobRoot) {
  const meta = readJobRequestMetadata(jobRoot);
  return {
    enableSpeech: meta.enableSpeech,
    enableEmbedVideo: meta.enableEmbedVideo,
  };
}

/**
 * @param {string} jobsRoot
 * @param {string} jobId
 */
export function readJobRequestOptionsById(jobsRoot, jobId) {
  return readJobRequestOptions(path.join(jobsRoot, jobId));
}
