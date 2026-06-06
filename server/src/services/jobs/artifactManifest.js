import fs from "node:fs";
import path from "node:path";

import { jobPathsFromRoot } from "../../config/jobs.js";
import { readJobRequestOptions } from "./readJobRequest.js";
import { readJobRecord } from "./readJob.js";
import { resolveStudyCardsArtifact } from "./resolveStudyCardsArtifact.js";

/** User-facing artifact kinds exposed in API / frontend downloads. */
const PRODUCT_ARTIFACT_KINDS = new Set(["renderedVideo", "studyCardsHtml"]);

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
 */
export async function listJobArtifacts(jobId) {
  const { paths } = await readJobRecord(jobId);
  const request = readJobRequestOptions(paths.root);
  const artifacts = [];

  const manifestEntries = readManifestFile(paths.root) ?? [];
  for (const entry of manifestEntries) {
    if (!PRODUCT_ARTIFACT_KINDS.has(String(entry.kind || ""))) continue;
    if (!fs.existsSync(entry.path)) continue;
    if (!request.enableSpeech && String(entry.kind) === "renderedVideo") continue;
    artifacts.push({
      kind: entry.kind,
      label: entry.label || entry.kind,
      downloadUrl: `/api/jobs/${encodeURIComponent(jobId)}/artifacts/${entry.kind}`,
      sizeBytes: fs.statSync(entry.path).size,
    });
  }

  const studyCards = await resolveStudyCardsArtifact(jobId, paths.root);
  if (
    studyCards.source === "db" &&
    studyCards.html &&
    !artifacts.some((a) => a.kind === "studyCardsHtml")
  ) {
    artifacts.push({
      kind: "studyCardsHtml",
      label: "studyCardsHtml",
      downloadUrl: `/api/jobs/${encodeURIComponent(jobId)}/artifacts/studyCardsHtml`,
      sizeBytes: Buffer.byteLength(studyCards.html, "utf8"),
    });
  }

  return artifacts;
}

/**
 * @param {string} jobId
 * @param {string} kind
 */
export async function resolveArtifactDownload(jobId, kind) {
  const { record, paths } = await readJobRecord(jobId);
  const request = readJobRequestOptions(paths.root);
  if (kind === "renderedVideo" && !request.enableSpeech) {
    const err = new Error("artifact not available");
    err.statusCode = 404;
    throw err;
  }
  if (!PRODUCT_ARTIFACT_KINDS.has(kind)) {
    const err = new Error("unknown artifact kind");
    err.statusCode = 404;
    throw err;
  }

  if (kind === "studyCardsHtml") {
    const resolved = await resolveStudyCardsArtifact(jobId, paths.root);
    if (resolved.source === "db" && resolved.html) {
      return { html: resolved.html, label: "study_cards.html" };
    }
    if (resolved.source === "disk" && resolved.path) {
      return resolvePathWithinJob(
        record.output_root,
        resolved.path,
        "study_cards.html"
      );
    }
    const err = new Error("artifact not available");
    err.statusCode = 404;
    throw err;
  }

  const manifestEntries = readManifestFile(paths.root);
  const entry = manifestEntries?.find((item) => item.kind === kind);
  if (!entry?.path) {
    const err = new Error("artifact not available");
    err.statusCode = 404;
    throw err;
  }

  return resolvePathWithinJob(record.output_root, entry.path, entry.label || kind);
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
