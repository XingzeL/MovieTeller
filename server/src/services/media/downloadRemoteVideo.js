import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

import { loadConfig } from "../../config/index.js";
import { VideoDownloadError } from "../billing/errors.js";
import { buildYtDlpFormatSelector } from "./buildYtDlpFormat.js";
import { downloadRemoteVideoViaIngest } from "./runVideoIngest.js";
import { buildYtDlpExtraArgs } from "./ytDlpOptions.js";

const DEFAULT_TIMEOUT_MS = 10 * 60 * 1000;
const DEFAULT_MAX_BYTES = 500 * 1024 * 1024;

/**
 * @param {typeof spawn} spawnFn
 * @param {string} cmd
 * @param {string[]} args
 * @param {number} timeoutMs
 * @param {{ onSpawn?: (child: import('node:child_process').ChildProcess) => void }} [behavior]
 */
function runCommandWithTimeout(spawnFn, cmd, args, timeoutMs, behavior = {}) {
  return new Promise((resolve, reject) => {
    const child = spawnFn(cmd, args, { stdio: ["ignore", "pipe", "pipe"] });
    behavior.onSpawn?.(child);
    let stdout = "";
    let stderr = "";
    const timer = setTimeout(() => {
      child.kill("SIGKILL");
      reject(new VideoDownloadError("video download timed out"));
    }, timeoutMs);

    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    child.on("error", (err) => {
      clearTimeout(timer);
      reject(new VideoDownloadError(String(err.message || err)));
    });
    child.on("close", (code) => {
      clearTimeout(timer);
      if (code !== 0) {
        reject(
          new VideoDownloadError(
            `yt-dlp failed (${code}): ${(stderr || stdout).trim().slice(0, 500)}`
          )
        );
        return;
      }
      resolve({ stdout, stderr });
    });
  });
}

/**
 * @param {string} outputDir
 */
function findDownloadedVideo(outputDir) {
  const entries = fs.readdirSync(outputDir, { withFileTypes: true });
  const files = entries
    .filter((entry) => entry.isFile())
    .map((entry) => entry.name)
    .filter((name) => !name.endsWith(".part") && !name.endsWith(".ytdl"));
  if (files.length === 0) {
    throw new VideoDownloadError("yt-dlp produced no output file");
  }
  if (files.length > 1) {
    const preferred = files.find((name) => name.startsWith("source."));
    if (preferred) {
      return path.join(outputDir, preferred);
    }
  }
  return path.join(outputDir, files[0]);
}

/**
 * @param {string} url
 * @param {string} outputDir
 * @param {{ ytDlpPath?: string, timeoutMs?: number, maxBytes?: number, spawnFn?: typeof spawn, preferIngest?: boolean, maxHeight?: number, title?: string | null, onSpawn?: (child: import('node:child_process').ChildProcess) => void }} [opts]
 * @returns {Promise<{ path: string, originalname: string, mimetype: string, size: number, title?: string | null, durationSec?: number | null }>}
 */
export async function downloadRemoteVideo(url, outputDir, opts = {}) {
  const config = loadConfig();
  const preferIngest = opts.preferIngest !== false;
  const maxHeight =
    opts.maxHeight ??
    (process.env.YT_DLP_MAX_HEIGHT
      ? Number(process.env.YT_DLP_MAX_HEIGHT)
      : 720);

  if (preferIngest && process.env.VIDEO_INGEST_DISABLED !== "1") {
    try {
      const ingested = await downloadRemoteVideoViaIngest(url, outputDir, {
        timeoutMs: opts.timeoutMs,
        maxHeight,
      });
      const maxBytes = opts.maxBytes ?? DEFAULT_MAX_BYTES;
      if (ingested.size > maxBytes) {
        try {
          fs.unlinkSync(ingested.path);
        } catch {
          /* ignore */
        }
        throw new VideoDownloadError("downloaded video exceeds size limit");
      }
      return ingested;
    } catch (err) {
      if (process.env.VIDEO_INGEST_REQUIRED === "1") {
        if (err instanceof VideoDownloadError) throw err;
        throw new VideoDownloadError(String(err?.message || err));
      }
      console.warn(
        "[downloadRemoteVideo] video_ingest failed, falling back to yt-dlp CLI:",
        err instanceof Error ? err.message : err
      );
    }
  }

  const ytDlpPath = opts.ytDlpPath || config.yt_dlp_path || "yt-dlp";
  const timeoutMs =
    opts.timeoutMs ??
    (process.env.VIDEO_DOWNLOAD_TIMEOUT_MS
      ? Number(process.env.VIDEO_DOWNLOAD_TIMEOUT_MS)
      : DEFAULT_TIMEOUT_MS);
  const maxBytes = opts.maxBytes ?? DEFAULT_MAX_BYTES;
  const maxFilesize = `${Math.floor(maxBytes / (1024 * 1024))}M`;
  const spawnFn = opts.spawnFn ?? spawn;

  fs.mkdirSync(outputDir, { recursive: true });
  const outputTemplate = path.join(outputDir, "source.%(ext)s");

  const args = [
    ...buildYtDlpExtraArgs(config, url),
    "--no-playlist",
    "--merge-output-format",
    "mp4",
    "-f",
    buildYtDlpFormatSelector({ maxHeight }),
    "--max-filesize",
    maxFilesize,
    "--socket-timeout",
    "30",
    "--print",
    "after_move:duration:%(duration)s",
    "-o",
    outputTemplate,
    url,
  ];

  let commandResult;
  try {
    commandResult = await runCommandWithTimeout(spawnFn, ytDlpPath, args, timeoutMs, {
      onSpawn: opts.onSpawn,
    });
  } catch (err) {
    if (err instanceof VideoDownloadError) {
      console.error("[downloadRemoteVideo] failed:", err.message);
      throw err;
    }
    throw new VideoDownloadError(String(err?.message || err));
  }

  let resolvedPath;
  try {
    resolvedPath = findDownloadedVideo(outputDir);
  } catch {
    throw new VideoDownloadError("downloaded video file is missing");
  }

  const stat = fs.statSync(resolvedPath);
  if (!stat.isFile() || stat.size <= 0) {
    throw new VideoDownloadError("downloaded video file is empty");
  }
  if (stat.size > maxBytes) {
    try {
      fs.unlinkSync(resolvedPath);
    } catch {
      /* ignore */
    }
    throw new VideoDownloadError("downloaded video exceeds size limit");
  }

  const ext = path.extname(resolvedPath).toLowerCase() || ".mp4";
  const title =
    opts.title != null && String(opts.title).trim()
      ? String(opts.title).trim()
      : null;
  const safeTitle = title
    ? `${title.replace(/[^\w.\-()\u4e00-\u9fff\s]+/g, "_").trim().slice(0, 80)}${ext}`
    : path.basename(resolvedPath) || `remote${ext}`;
  const durationSec = parseYtDlpDurationFromStdout(commandResult?.stdout);

  return {
    path: resolvedPath,
    originalname: safeTitle,
    mimetype: "video/mp4",
    size: stat.size,
    title,
    durationSec,
  };
}

/**
 * @param {string | undefined} stdout
 */
export function parseYtDlpDurationFromStdout(stdout) {
  const lines = String(stdout || "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  for (let i = lines.length - 1; i >= 0; i -= 1) {
    const match = /^duration:(.+)$/.exec(lines[i]);
    if (!match) continue;
    const value = Number(match[1]);
    return Number.isFinite(value) && value > 0 ? value : null;
  }
  return null;
}

/**
 * @param {string} dir
 */
export function removeDownloadDir(dir) {
  if (!dir) return;
  try {
    fs.rmSync(dir, { recursive: true, force: true });
  } catch {
    /* ignore */
  }
}
