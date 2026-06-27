/**
 * YouTube download integration (opt-in).
 *
 * YouTube often requires cookies (bot check: "Sign in to confirm you're not a bot").
 *
 * Run locally (recommended — no macOS keychain prompts):
 *   YT_DLP_COOKIES=secrets/yt-dlp-cookies.txt RUN_YOUTUBE_DOWNLOAD_INTEGRATION=1 npm run test:integration:youtube
 *
 * Fallback (may prompt for Chrome keychain on macOS):
 *   YT_DLP_COOKIES_FROM_BROWSER=chrome RUN_YOUTUBE_DOWNLOAD_INTEGRATION=1 npm run test:integration:youtube
 */
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import { loadConfig } from "../src/config/index.js";
import { downloadRemoteVideo } from "../src/services/media/downloadRemoteVideo.js";
import { parseRemoteVideo } from "../src/services/media/parseRemoteVideo.js";
import {
  validateSourceUrl,
  validateSourceUrlAsync,
} from "../src/services/media/validateSourceUrl.js";
import {
  YOUTUBE_NASA_EARTH_SOUND_DURATION_SEC,
  YOUTUBE_NASA_EARTH_SOUND_TITLE_PREFIX,
  YOUTUBE_NASA_EARTH_SOUND_URL,
  YOUTUBE_NASA_EARTH_SOUND_VIDEO_ID,
} from "./fixtures/youtubeUrls.js";

loadConfig();

const RUN =
  process.env.RUN_YOUTUBE_DOWNLOAD_INTEGRATION === "1" ||
  process.env.RUN_YOUTUBE_DOWNLOAD_INTEGRATION === "true";

const hasCookies =
  Boolean(process.env.YT_DLP_COOKIES?.trim()) ||
  Boolean(process.env.YT_DLP_COOKIES_FROM_BROWSER?.trim());

const describeIntegration = RUN ? test : test.skip;

describeIntegration("YouTube -oH3qIDmqTA integration", async (t) => {
  if (!hasCookies) {
    t.skip(
      "Set YT_DLP_COOKIES (e.g. secrets/yt-dlp-cookies.txt) for YouTube download; see secrets/README.md"
    );
    return;
  }

  const tempDirs = [];
  t.before(() => {
    process.env.VIDEO_INGEST_DISABLED = "1";
  });
  t.after(() => {
    for (const dir of tempDirs.splice(0)) {
      fs.rmSync(dir, { recursive: true, force: true });
    }
    delete process.env.VIDEO_INGEST_DISABLED;
  });

  await t.test("validateSourceUrl accepts youtube URL", async () => {
    const sync = validateSourceUrl(YOUTUBE_NASA_EARTH_SOUND_URL);
    assert.equal(sync.ok, true);
    const asyncResult = await validateSourceUrlAsync(YOUTUBE_NASA_EARTH_SOUND_URL);
    assert.equal(asyncResult.ok, true);
  });

  await t.test("parseRemoteVideo returns metadata", async () => {
    const parsed = await parseRemoteVideo(YOUTUBE_NASA_EARTH_SOUND_URL, {
      timeoutMs: 120_000,
      preferIngest: false,
    });
    assert.equal(parsed.id, YOUTUBE_NASA_EARTH_SOUND_VIDEO_ID);
    assert.ok(
      parsed.title?.includes(YOUTUBE_NASA_EARTH_SOUND_TITLE_PREFIX),
      `unexpected title: ${parsed.title}`
    );
    assert.equal(parsed.duration, YOUTUBE_NASA_EARTH_SOUND_DURATION_SEC);
    assert.equal(parsed.platform, "youtube");
  });

  await t.test("downloadRemoteVideo downloads video to mp4", async () => {
    const outputDir = fs.mkdtempSync(path.join(os.tmpdir(), "movieteller_yt_test_"));
    tempDirs.push(outputDir);

    const result = await downloadRemoteVideo(YOUTUBE_NASA_EARTH_SOUND_URL, outputDir, {
      timeoutMs: 10 * 60 * 1000,
      maxHeight: 720,
      preferIngest: false,
    });

    assert.ok(fs.existsSync(result.path), "downloaded file missing");
    assert.match(result.originalname, /\.mp4$/i);
    assert.ok(result.size > 500_000, `file too small: ${result.size}`);
  });
});
