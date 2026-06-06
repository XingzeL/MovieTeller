import { spawn } from "node:child_process";
import path from "node:path";

import { loadConfig } from "../../config/index.js";
import { VideoProbeError } from "../billing/errors.js";

/**
 * @param {string} ffmpegPath
 */
export function ffprobePathFor(ffmpegPath) {
  const base = path.basename(ffmpegPath);
  if (base === "ffmpeg") {
    return path.join(path.dirname(ffmpegPath), "ffprobe");
  }
  return "ffprobe";
}

/**
 * @param {string} cmd
 * @param {string[]} args
 * @param {number} timeoutMs
 */
function runCommandWithTimeout(cmd, args, timeoutMs) {
  return new Promise((resolve, reject) => {
    const child = spawn(cmd, args, { stdio: ["ignore", "pipe", "pipe"] });
    let stdout = "";
    let stderr = "";
    const timer = setTimeout(() => {
      child.kill("SIGKILL");
      reject(new VideoProbeError("video probe timed out"));
    }, timeoutMs);

    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    child.on("error", (err) => {
      clearTimeout(timer);
      reject(new VideoProbeError(String(err.message || err)));
    });
    child.on("close", (code) => {
      clearTimeout(timer);
      if (code !== 0) {
        reject(
          new VideoProbeError(
            `ffprobe failed (${code}): ${(stderr || stdout).trim().slice(0, 200)}`
          )
        );
        return;
      }
      resolve(stdout);
    });
  });
}

/**
 * @param {string} mediaPath
 * @param {{ ffprobePath?: string, timeoutMs?: number }} [opts]
 * @returns {Promise<number>} duration in seconds (rounded up to int)
 */
export async function probeDurationSec(mediaPath, opts = {}) {
  const config = loadConfig();
  const ffmpegPath = opts.ffmpegPath || config.ffmpeg_path || "ffmpeg";
  const ffprobePath = opts.ffprobePath || ffprobePathFor(ffmpegPath);
  const timeoutMs = opts.timeoutMs ?? 30_000;

  let stdout;
  try {
    stdout = await runCommandWithTimeout(
      ffprobePath,
      [
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        mediaPath,
      ],
      timeoutMs
    );
  } catch (err) {
    if (err instanceof VideoProbeError) throw err;
    throw new VideoProbeError(String(err?.message || err));
  }

  const raw = String(stdout || "").trim();
  const value = Number(raw);
  if (!raw || !Number.isFinite(value) || value <= 0) {
    throw new VideoProbeError("ffprobe returned invalid duration");
  }
  return Math.ceil(value);
}
