import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

import { loadConfig } from "../../config/index.js";
import { VideoDownloadError } from "../billing/errors.js";
import { buildYtDlpExtraArgs } from "./ytDlpOptions.js";

const DEFAULT_TIMEOUT_MS = 10 * 60 * 1000;
const DEFAULT_MAX_BYTES = 500 * 1024 * 1024;

/**
 * @param {typeof spawn} spawnFn
 * @param {string} cmd
 * @param {string[]} args
 * @param {number} timeoutMs
 */
function runCommandWithTimeout(spawnFn, cmd, args, timeoutMs) {
  return new Promise((resolve, reject) => {
    const child = spawnFn(cmd, args, { stdio: ["ignore", "pipe", "pipe"] });
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
 * @param {{ ytDlpPath?: string, timeoutMs?: number, maxBytes?: number, spawnFn?: typeof spawn }} [opts]
 * @returns {Promise<{ path: string, originalname: string, mimetype: string, size: number, title?: string | null }>}
 */
export async function downloadRemoteVideo(url, outputDir, opts = {}) {
  const config = loadConfig();
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
    "bv*+ba/b",
    "--max-filesize",
    maxFilesize,
    "--socket-timeout",
    "30",
    "-o",
    outputTemplate,
    "--print",
    "title",
    "--print",
    "filename",
    url,
  ];

  let stdout;
  try {
    ({ stdout } = await runCommandWithTimeout(spawnFn, ytDlpPath, args, timeoutMs));
  } catch (err) {
    if (err instanceof VideoDownloadError) {
      console.error("[downloadRemoteVideo] failed:", err.message);
      throw err;
    }
    throw new VideoDownloadError(String(err?.message || err));
  }

  const lines = String(stdout || "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  const downloadedPath =
    lines.length > 0 ? lines[lines.length - 1] : findDownloadedVideo(outputDir);
  const resolvedPath = path.isAbsolute(downloadedPath)
    ? downloadedPath
    : path.join(outputDir, downloadedPath);

  if (!fs.existsSync(resolvedPath)) {
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
  const title = lines.length >= 2 ? lines[0] : null;
  const safeTitle = title
    ? `${title.replace(/[^\w.\-()\u4e00-\u9fff\s]+/g, "_").trim().slice(0, 80)}${ext}`
    : `remote${ext}`;

  return {
    path: resolvedPath,
    originalname: safeTitle,
    mimetype: "video/mp4",
    size: stat.size,
    title,
  };
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
