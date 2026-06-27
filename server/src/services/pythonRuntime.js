import fs from "fs";
import path from "path";

import { getRepoRoot } from "../config/index.js";
import { resolveYtDlpCookiesPath } from "./media/ytDlpOptions.js";

const PYTHON_SRC_PACKAGES = [
  "movieteller_config",
  "movieteller_logging",
  "pipeline_types",
  "media_utils",
  "model_gateway",
  "subtitle_extraction",
  "subtitle_analysis",
  "frame_source",
  "narration",
  "narration_polish",
  "narration_speech",
  "narration_video",
  "pipeline_transcript",
  "rerank",
  "video_render",
  "subtitle_context",
  "video_frame_pool",
  "video_ingest",
  "movie_pipeline",
];

/**
 * @param {string} repoRoot
 * @param {string | undefined} explicitPython
 */
export function resolveProjectPython(repoRoot, explicitPython) {
  if (explicitPython) return explicitPython;
  if (process.env.MOVIE_TELLER_PYTHON) return process.env.MOVIE_TELLER_PYTHON;
  const repoVenvPython = path.join(repoRoot, ".venv", "bin", "python3");
  return fs.existsSync(repoVenvPython) ? repoVenvPython : "python3";
}

/** @param {string} repoRoot */
export function buildPythonEnv(repoRoot) {
  const repoVenvBin = path.join(repoRoot, ".venv", "bin");
  const pythonPathEntries = PYTHON_SRC_PACKAGES.map((pkg) =>
    path.join(repoRoot, "python", pkg, "src")
  );
  if (process.env.PYTHONPATH) {
    pythonPathEntries.push(process.env.PYTHONPATH);
  }

  const env = {
    ...process.env,
    PYTHONPATH: pythonPathEntries.join(path.delimiter),
    MOVIE_TELLER_REPO_ROOT: repoRoot,
  };

  const cookies = process.env.YT_DLP_COOKIES?.trim();
  if (cookies) {
    env.YT_DLP_COOKIES = resolveYtDlpCookiesPath(cookies);
  }

  if (fs.existsSync(repoVenvBin)) {
    env.PATH = [repoVenvBin, process.env.PATH || ""].filter(Boolean).join(path.delimiter);
  }
  return env;
}

/** @returns {{ repoRoot: string, python: string, env: NodeJS.ProcessEnv }} */
export function resolvePythonRuntime(opts = {}) {
  const repoRoot = getRepoRoot();
  return {
    repoRoot,
    python: resolveProjectPython(repoRoot, opts.pythonExe),
    env: buildPythonEnv(repoRoot),
  };
}
