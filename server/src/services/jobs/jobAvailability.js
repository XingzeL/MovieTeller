import fs from "node:fs";

import { jobPathsFromRoot } from "../../config/jobs.js";

/**
 * @param {string} jobRoot
 */
function readManifestEntries(jobRoot) {
  const manifestPath = jobPathsFromRoot(jobRoot).artifactManifestPath;
  if (!fs.existsSync(manifestPath)) return null;
  try {
    const raw = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
    return Array.isArray(raw) ? raw : null;
  } catch {
    return null;
  }
}

/**
 * @param {string} jobRoot
 * @param {string} kind
 */
function manifestArtifactExists(jobRoot, kind) {
  const entries = readManifestEntries(jobRoot);
  if (!entries) return false;
  const entry = entries.find((e) => e && e.kind === kind && e.path);
  return entry ? fs.existsSync(entry.path) : false;
}

/**
 * @param {string} jobRoot
 */
function studyCardsExists(jobRoot) {
  return manifestArtifactExists(jobRoot, "studyCardsHtml");
}

/**
 * @param {string} jobRoot
 */
function renderedVideoExists(jobRoot) {
  return manifestArtifactExists(jobRoot, "renderedVideo");
}

/**
 * @param {Record<string, unknown>} record
 * @param {import("./readJobRequest.js").JobRequestMetadata} request
 * @param {string} jobRoot
 */
export function buildJobAvailability(record, request = {}, jobRoot) {
  const enableSpeech = request.enableSpeech !== false;
  const status = String(record.status || "");
  const downloaded = Boolean(record.video_downloaded_at);
  const purged = Boolean(record.video_purged_at);

  /** @type {"not_generated" | "disabled" | "available" | "downloaded" | "purged"} */
  let videoState = "not_generated";

  if (!enableSpeech) {
    videoState = "not_generated";
  } else if (purged) {
    videoState = "purged";
  } else if (downloaded) {
    videoState = "downloaded";
  } else if (status === "succeeded" && renderedVideoExists(jobRoot)) {
    videoState = "available";
  } else {
    videoState = "not_generated";
  }

  const canDownloadVideo = videoState === "available";
  const canOpenStudyCards =
    status === "succeeded" && studyCardsExists(jobRoot);

  return {
    videoState,
    canDownloadVideo,
    canOpenStudyCards,
  };
}
