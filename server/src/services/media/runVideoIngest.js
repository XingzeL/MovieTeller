import { spawn } from "node:child_process";

import { getRepoRoot } from "../../config/index.js";
import { VideoDownloadError, VideoParseError } from "../billing/errors.js";
import {
  buildPythonEnv,
  resolveProjectPython,
} from "../pythonRuntime.js";

const DEFAULT_PARSE_TIMEOUT_MS = 60_000;
const DEFAULT_DOWNLOAD_TIMEOUT_MS = 10 * 60 * 1000;

/**
 * @param {string} python
 * @param {string[]} args
 * @param {NodeJS.ProcessEnv} env
 * @param {string} repoRoot
 * @param {number} timeoutMs
 */
function runPythonJson(python, args, env, repoRoot, timeoutMs) {
  return new Promise((resolve, reject) => {
    const proc = spawn(python, args, { env, cwd: repoRoot });
    const outChunks = [];
    const errChunks = [];
    const timer = setTimeout(() => {
      proc.kill("SIGKILL");
      reject(new Error("video_ingest timed out"));
    }, timeoutMs);

    proc.stdout.on("data", (d) => outChunks.push(d));
    proc.stderr.on("data", (d) => errChunks.push(d));
    proc.on("error", (err) => {
      clearTimeout(timer);
      reject(err);
    });
    proc.on("close", (code) => {
      clearTimeout(timer);
      const out = Buffer.concat(outChunks).toString("utf8");
      const errTxt = Buffer.concat(errChunks).toString("utf8");
      if (code !== 0) {
        reject(new Error(errTxt || out || `exit ${code}`));
        return;
      }
      try {
        const trimmed = out.trim();
        if (!trimmed) {
          reject(new Error("video_ingest produced empty stdout"));
          return;
        }
        resolve(JSON.parse(trimmed));
      } catch (e) {
        reject(new Error(`Invalid JSON from video_ingest: ${out.slice(0, 500)}`));
      }
    });
  });
}

/**
 * @param {string} url
 * @param {{ timeoutMs?: number, pythonExe?: string }} [opts]
 */
export async function parseRemoteVideoViaIngest(url, opts = {}) {
  const repoRoot = getRepoRoot();
  const python = resolveProjectPython(repoRoot, opts.pythonExe);
  const env = buildPythonEnv(repoRoot);
  const timeoutMs = opts.timeoutMs ?? DEFAULT_PARSE_TIMEOUT_MS;
  try {
    const payload = await runPythonJson(
      python,
      ["-m", "video_ingest", "parse", "--url", url, "--json"],
      env,
      repoRoot,
      timeoutMs
    );
    return {
      id: payload.id != null ? String(payload.id) : null,
      title: payload.title != null ? String(payload.title) : null,
      thumbnail: payload.thumbnail != null ? String(payload.thumbnail) : null,
      duration:
        payload.duration != null && Number(payload.duration) > 0
          ? Number(payload.duration)
          : null,
      platform: payload.platform != null ? String(payload.platform) : null,
      uploader: payload.uploader != null ? String(payload.uploader) : null,
    };
  } catch (err) {
    throw new VideoParseError(String(err?.message || err));
  }
}

/**
 * @param {string} url
 * @param {string} outputDir
 * @param {{ timeoutMs?: number, pythonExe?: string, maxHeight?: number }} [opts]
 */
export async function downloadRemoteVideoViaIngest(url, outputDir, opts = {}) {
  const repoRoot = getRepoRoot();
  const python = resolveProjectPython(repoRoot, opts.pythonExe);
  const env = buildPythonEnv(repoRoot);
  const timeoutMs = opts.timeoutMs ?? DEFAULT_DOWNLOAD_TIMEOUT_MS;
  const args = [
    "-m",
    "video_ingest",
    "download",
    "--url",
    url,
    "--output-dir",
    outputDir,
    "--json",
  ];
  if (opts.maxHeight != null && Number(opts.maxHeight) > 0) {
    args.push("--max-height", String(Math.floor(opts.maxHeight)));
  }
  try {
    const payload = await runPythonJson(
      python,
      args,
      env,
      repoRoot,
      timeoutMs
    );
    if (!payload?.path) {
      throw new VideoDownloadError("video_ingest download returned no path");
    }
    return {
      path: String(payload.path),
      originalname: String(payload.originalname || payload.filename || "remote.mp4"),
      mimetype: String(payload.mimetype || "video/mp4"),
      size: Number(payload.size) || 0,
      title: payload.title != null ? String(payload.title) : null,
      durationSec:
        payload.duration != null && Number(payload.duration) > 0
          ? Number(payload.duration)
          : null,
    };
  } catch (err) {
    if (err instanceof VideoDownloadError) throw err;
    throw new VideoDownloadError(String(err?.message || err));
  }
}
