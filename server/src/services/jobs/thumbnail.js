import fs from "node:fs";
import path from "node:path";

import { readJobRecord } from "./readJob.js";

/**
 * @param {string} root
 * @param {string} candidate
 */
function assertPathInside(root, candidate) {
  const resolvedRoot = path.resolve(root);
  const resolvedCandidate = path.resolve(candidate);
  if (
    resolvedCandidate !== resolvedRoot &&
    !resolvedCandidate.startsWith(resolvedRoot + path.sep)
  ) {
    const err = new Error("thumbnail path not allowed");
    err.statusCode = 403;
    throw err;
  }
  return resolvedCandidate;
}

/**
 * @param {string} jobId
 */
export async function resolveJobThumbnail(jobId) {
  const { paths } = await readJobRecord(jobId);
  const framePoolRoot = path.join(paths.root, "frame_pool");
  const manifestPath = path.join(framePoolRoot, "manifest.jsonl");

  if (!fs.existsSync(manifestPath)) {
    const err = new Error("thumbnail not available");
    err.statusCode = 404;
    throw err;
  }

  const raw = fs.readFileSync(manifestPath, "utf8");
  const firstLine = raw.split(/\r?\n/).find((line) => line.trim());
  if (!firstLine) {
    const err = new Error("thumbnail not available");
    err.statusCode = 404;
    throw err;
  }

  let row;
  try {
    row = JSON.parse(firstLine);
  } catch {
    const err = new Error("thumbnail manifest invalid");
    err.statusCode = 500;
    throw err;
  }

  const imageRef = String(row.imageRef || "").trim();
  if (!imageRef) {
    const err = new Error("thumbnail not available");
    err.statusCode = 404;
    throw err;
  }

  const filePath = assertPathInside(framePoolRoot, path.join(framePoolRoot, imageRef));
  if (!fs.existsSync(filePath)) {
    const err = new Error("thumbnail file missing");
    err.statusCode = 404;
    throw err;
  }

  return { filePath };
}
