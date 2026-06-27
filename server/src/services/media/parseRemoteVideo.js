import { spawn } from "node:child_process";

import { loadConfig } from "../../config/index.js";
import { VideoParseError } from "../billing/errors.js";
import { buildYtDlpExtraArgs } from "./ytDlpOptions.js";
import { parseRemoteVideoViaIngest } from "./runVideoIngest.js";

const DEFAULT_TIMEOUT_MS = 60_000;

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
      reject(new VideoParseError("video parse timed out"));
    }, timeoutMs);

    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    child.on("error", (err) => {
      clearTimeout(timer);
      reject(new VideoParseError(String(err.message || err)));
    });
    child.on("close", (code) => {
      clearTimeout(timer);
      if (code !== 0) {
        reject(
          new VideoParseError(
            `yt-dlp parse failed (${code}): ${(stderr || stdout).trim().slice(0, 500)}`
          )
        );
        return;
      }
      resolve({ stdout, stderr });
    });
  });
}

/**
 * @param {Record<string, unknown>} info
 */
function normalizeParsedInfo(info) {
  const durationRaw = info.duration;
  const duration =
    durationRaw == null || durationRaw === ""
      ? null
      : Number(durationRaw);
  return {
    id: info.id != null ? String(info.id) : null,
    title: info.title != null ? String(info.title) : null,
    thumbnail: info.thumbnail != null ? String(info.thumbnail) : null,
    duration: Number.isFinite(duration) && duration > 0 ? duration : null,
    platform:
      (info.extractor != null && String(info.extractor)) ||
      (info.extractor_key != null && String(info.extractor_key)) ||
      null,
    uploader:
      (info.uploader != null && String(info.uploader)) ||
      (info.channel != null && String(info.channel)) ||
      null,
  };
}

/**
 * @param {ReturnType<typeof normalizeParsedInfo>} base
 * @param {ReturnType<typeof normalizeParsedInfo>} supplement
 */
function mergeParsedResults(base, supplement) {
  const duration =
    base.duration && base.duration > 0
      ? base.duration
      : supplement.duration && supplement.duration > 0
        ? supplement.duration
        : null;
  return {
    id: base.id ?? supplement.id,
    title: base.title ?? supplement.title,
    thumbnail: base.thumbnail ?? supplement.thumbnail,
    duration,
    platform: base.platform ?? supplement.platform,
    uploader: base.uploader ?? supplement.uploader,
  };
}

/**
 * @param {string} url
 * @param {{ ytDlpPath?: string, timeoutMs?: number, spawnFn?: typeof spawn }} opts
 */
async function parseRemoteVideoViaCli(url, opts = {}) {
  const config = loadConfig();
  const ytDlpPath = opts.ytDlpPath || config.yt_dlp_path || "yt-dlp";
  const timeoutMs =
    opts.timeoutMs ??
    (process.env.VIDEO_PARSE_TIMEOUT_MS
      ? Number(process.env.VIDEO_PARSE_TIMEOUT_MS)
      : DEFAULT_TIMEOUT_MS);
  const spawnFn = opts.spawnFn ?? spawn;

  const args = [
    ...buildYtDlpExtraArgs(config, url),
    "--no-playlist",
    "--skip-download",
    "--dump-single-json",
    "--no-warnings",
    url,
  ];

  const { stdout } = await runCommandWithTimeout(
    spawnFn,
    ytDlpPath,
    args,
    timeoutMs
  );

  try {
    const info = JSON.parse(String(stdout || "").trim());
    return normalizeParsedInfo(info);
  } catch {
    throw new VideoParseError("yt-dlp returned invalid JSON");
  }
}

/**
 * @param {string} url
 * @param {{ ytDlpPath?: string, timeoutMs?: number, spawnFn?: typeof spawn, preferIngest?: boolean }} [opts]
 */
export async function parseRemoteVideo(url, opts = {}) {
  const preferIngest = opts.preferIngest !== false;
  let ingestResult = null;

  if (preferIngest && process.env.VIDEO_INGEST_DISABLED !== "1") {
    try {
      ingestResult = await parseRemoteVideoViaIngest(url, {
        timeoutMs: opts.timeoutMs,
      });
      if (ingestResult.duration && ingestResult.duration > 0) {
        return ingestResult;
      }
      console.warn(
        "[parseRemoteVideo] video_ingest missing duration, supplementing via yt-dlp CLI"
      );
    } catch (err) {
      if (process.env.VIDEO_INGEST_REQUIRED === "1") {
        throw err;
      }
      console.warn(
        "[parseRemoteVideo] video_ingest failed, falling back to yt-dlp CLI:",
        err instanceof Error ? err.message : err
      );
    }
  }

  try {
    const cliResult = await parseRemoteVideoViaCli(url, opts);
    if (ingestResult) {
      return mergeParsedResults(ingestResult, cliResult);
    }
    return cliResult;
  } catch (err) {
    if (ingestResult?.title) {
      return ingestResult;
    }
    if (err instanceof VideoParseError) throw err;
    throw new VideoParseError(String(err?.message || err));
  }
}
