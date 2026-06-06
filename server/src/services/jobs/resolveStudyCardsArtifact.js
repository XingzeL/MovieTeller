import fs from "node:fs";

import { isDbEnabled } from "../../db/database.js";
import { getStudyCardsByJobId } from "../../db/studyCardsRepository.js";
import { jobPathsFromRoot } from "../../config/jobs.js";

/**
 * @param {string} jobRoot
 */
function readManifestStudyCardsPath(jobRoot) {
  const manifestPath = jobPathsFromRoot(jobRoot).artifactManifestPath;
  if (!fs.existsSync(manifestPath)) return null;
  try {
    const raw = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
    if (!Array.isArray(raw)) return null;
    const entry = raw.find((e) => e && e.kind === "studyCardsHtml" && e.path);
    if (!entry?.path || !fs.existsSync(entry.path)) return null;
    return String(entry.path);
  } catch {
    return null;
  }
}

/**
 * @param {string} jobId
 * @param {string} [jobRoot]
 * @returns {Promise<{ source: 'db' | 'disk' | 'none', html?: string, path?: string }>}
 */
export async function resolveStudyCardsArtifact(jobId, jobRoot = "") {
  if (isDbEnabled()) {
    const row = await getStudyCardsByJobId(jobId);
    if (row?.html) {
      return { source: "db", html: String(row.html) };
    }
  }

  if (jobRoot) {
    const diskPath = readManifestStudyCardsPath(jobRoot);
    if (diskPath) {
      return { source: "disk", path: diskPath };
    }
  }

  return { source: "none" };
}
