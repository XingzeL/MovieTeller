import fs from "fs";
import { spawn } from "child_process";
import path from "path";

import { getRepoRoot } from "../../config/index.js";

function resolveProjectPython(repoRoot, explicitPython) {
  if (explicitPython) return explicitPython;
  if (process.env.MOVIE_TELLER_PYTHON) return process.env.MOVIE_TELLER_PYTHON;

  const repoVenvPython = path.join(repoRoot, ".venv", "bin", "python3");
  return fs.existsSync(repoVenvPython) ? repoVenvPython : "python3";
}

function buildPythonEnv(repoRoot) {
  const repoVenvBin = path.join(repoRoot, ".venv", "bin");
  const pythonPathEntries = [
    path.join(repoRoot, "python/movieteller_config/src"),
    path.join(repoRoot, "python/subtitle_extraction/src"),
    process.env.PYTHONPATH || "",
  ].filter(Boolean);

  const env = {
    ...process.env,
    PYTHONPATH: pythonPathEntries.join(path.delimiter),
  };

  if (fs.existsSync(repoVenvBin)) {
    env.PATH = [repoVenvBin, process.env.PATH || ""].filter(Boolean).join(path.delimiter);
  }
  return env;
}

/**
 * Run Python ``python -m subtitle_extraction --video ... --output-srt ... --json``.
 *
 * @param {string} videoPath absolute path to media file
 * @param {{ outputSrtPath: string, pythonExe?: string }} opts
 * @returns {Promise<{ subtitlePath: string, cues: Array<{ startSec: number, endSec: number, text: string }> }>}
 */
export function extractSubtitlesFromVideoFile(videoPath, opts) {
  const repoRoot = getRepoRoot();
  const python = resolveProjectPython(repoRoot, opts.pythonExe);
  const env = buildPythonEnv(repoRoot);
  const args = [
    "-m",
    "subtitle_extraction",
    "--video",
    videoPath,
    "--output-srt",
    opts.outputSrtPath,
    "--json",
  ];
  return new Promise((resolve, reject) => {
    const chunks = [];
    const errChunks = [];
    const proc = spawn(python, args, { env, cwd: repoRoot });
    proc.stdout.on("data", (d) => chunks.push(d));
    proc.stderr.on("data", (d) => errChunks.push(d));
    proc.on("error", reject);
    proc.on("close", (code) => {
      const out = Buffer.concat(chunks).toString("utf8");
      const errTxt = Buffer.concat(errChunks).toString("utf8");
      if (code !== 0) {
        reject(new Error(`subtitle_extraction failed (exit ${code}): ${errTxt || out || "(no output)"}`));
        return;
      }
      try {
        const trimmed = out.trim();
        if (!trimmed) {
          reject(new Error("subtitle_extraction produced empty stdout"));
          return;
        }
        resolve(JSON.parse(trimmed));
      } catch (e) {
        reject(new Error(`Invalid JSON from subtitle_extraction: ${out.slice(0, 500)}`));
      }
    });
  });
}
