import fs from "node:fs";
import path from "node:path";

import { jobPathsFromRoot } from "../../config/jobs.js";
import { readJobRecord } from "./readJob.js";

/** @deprecated fallback only — prefer artifacts/manifest.json from Python */
const LEGACY_ARTIFACT_KINDS = {
  sourceVideo: { label: "Source video", pathKeys: ["videoPath"] },
  extractedSrt: { label: "Extracted subtitles", pathKeys: ["srtPath"] },
  finalSrt: { label: "Final subtitles", pathKeys: ["finalSrtPath"] },
  narrationJson: { label: "Narration JSON", pathKeys: ["textJsonPath"] },
  speechJson: { label: "Speech manifest", pathKeys: ["speechJsonPath"] },
  renderedVideo: {
    label: "Rendered video",
    pathKeys: ["renderedVideoPath", "renderJsonPath"],
  },
  studyCardsHtml: { label: "Study cards", pathKeys: ["studyCardsHtmlPath"] },
  framePoolManifest: {
    label: "Frame pool manifest",
    pathKeys: ["framePoolManifest"],
  },
};

/**
 * @param {string} jobRoot
 * @returns {Array<{ kind: string, label: string, path: string, mediaType?: string }> | null}
 */
function readManifestFile(jobRoot) {
  const manifestPath = jobPathsFromRoot(jobRoot).artifactManifestPath;
  if (!fs.existsSync(manifestPath)) {
    return null;
  }
  try {
    const raw = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
    if (!Array.isArray(raw)) return null;
    return raw.filter((entry) => entry && typeof entry === "object" && entry.path);
  } catch {
    return null;
  }
}

/**
 * @param {string} jobId
 * @param {string} outputRoot
 * @param {Record<string, unknown>} artifacts
 */
function listFromLegacyArtifacts(jobId, outputRoot, artifacts) {
  const items = [];
  const jobRootResolved = path.resolve(outputRoot);
  for (const [kind, meta] of Object.entries(LEGACY_ARTIFACT_KINDS)) {
    let filePath = null;
    for (const key of meta.pathKeys) {
      const candidate = artifacts[key];
      if (candidate && fs.existsSync(candidate)) {
        filePath = candidate;
        break;
      }
    }
    if (!filePath) continue;
    const resolved = path.resolve(String(filePath));
    if (
      !resolved.startsWith(jobRootResolved + path.sep) &&
      resolved !== jobRootResolved
    ) {
      continue;
    }
    items.push({
      kind,
      label: meta.label,
      path: resolved,
      downloadUrl: `/api/jobs/${encodeURIComponent(jobId)}/artifacts/${kind}`,
      sizeBytes: fs.statSync(resolved).size,
    });
  }
  return items;
}

/**
 * @param {string} jobId
 */
export function listJobArtifacts(jobId) {
  const { record, paths } = readJobRecord(jobId);
  const manifestEntries = readManifestFile(paths.root);
  if (manifestEntries && manifestEntries.length > 0) {
    return manifestEntries
      .filter((entry) => fs.existsSync(entry.path))
      .map((entry) => ({
        kind: entry.kind,
        label: entry.label || entry.kind,
        downloadUrl: `/api/jobs/${encodeURIComponent(jobId)}/artifacts/${entry.kind}`,
        sizeBytes: fs.statSync(entry.path).size,
      }));
  }
  return listFromLegacyArtifacts(
    jobId,
    record.output_root,
    record.artifacts || {}
  );
}

/**
 * @param {string} jobId
 * @param {string} kind
 */
export function resolveArtifactDownload(jobId, kind) {
  const { record, paths } = readJobRecord(jobId);
  const manifestEntries = readManifestFile(paths.root);
  if (manifestEntries) {
    const entry = manifestEntries.find((item) => item.kind === kind);
    if (!entry?.path) {
      const err = new Error("artifact not available");
      err.statusCode = 404;
      throw err;
    }
    return resolvePathWithinJob(record.output_root, entry.path, entry.label || kind);
  }

  if (!Object.prototype.hasOwnProperty.call(LEGACY_ARTIFACT_KINDS, kind)) {
    const err = new Error("unknown artifact kind");
    err.statusCode = 404;
    throw err;
  }
  const meta = LEGACY_ARTIFACT_KINDS[kind];
  const artifacts = record.artifacts || {};
  let filePath = null;
  for (const key of meta.pathKeys) {
    const candidate = artifacts[key];
    if (candidate && fs.existsSync(candidate)) {
      filePath = candidate;
      break;
    }
  }
  if (!filePath) {
    const err = new Error("artifact not available");
    err.statusCode = 404;
    throw err;
  }
  return resolvePathWithinJob(record.output_root, filePath, meta.label);
}

/**
 * @param {string} outputRoot
 * @param {string} filePath
 * @param {string} label
 */
function resolvePathWithinJob(outputRoot, filePath, label) {
  const resolved = path.resolve(filePath);
  const jobRoot = path.resolve(outputRoot);
  if (!resolved.startsWith(jobRoot + path.sep) && resolved !== jobRoot) {
    const err = new Error("artifact path not allowed");
    err.statusCode = 403;
    throw err;
  }
  if (!fs.existsSync(resolved)) {
    const err = new Error("artifact file missing");
    err.statusCode = 404;
    throw err;
  }
  return { filePath: resolved, label };
}
