/**
 * Bilibili download integration (opt-in).
 *
 * BV1Yx411578x requires cookies for yt-dlp download (HTTP 412 without them).
 *
 * Run locally (recommended — no macOS keychain prompts):
 *   YT_DLP_COOKIES=secrets/yt-dlp-cookies.txt RUN_BILIBILI_DOWNLOAD_INTEGRATION=1 npm run test:integration:bilibili
 *
 * Fallback (may prompt for Chrome keychain on macOS):
 *   YT_DLP_COOKIES_FROM_BROWSER=chrome RUN_BILIBILI_DOWNLOAD_INTEGRATION=1 npm run test:integration:bilibili
 */
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import { loadConfig } from "../src/config/index.js";
import { parseRemoteVideo } from "../src/services/media/parseRemoteVideo.js";
import { downloadRemoteVideo } from "../src/services/media/downloadRemoteVideo.js";
import {
  validateSourceUrl,
  validateSourceUrlAsync,
} from "../src/services/media/validateSourceUrl.js";
import {
  BILIBILI_PEPPA_CHONGQING_BVID,
  BILIBILI_PEPPA_CHONGQING_DURATION_SEC,
  BILIBILI_PEPPA_CHONGQING_TITLE_PREFIX,
  BILIBILI_PEPPA_CHONGQING_URL,
} from "./fixtures/bilibiliUrls.js";

loadConfig();

const RUN =
  process.env.RUN_BILIBILI_DOWNLOAD_INTEGRATION === "1" ||
  process.env.RUN_BILIBILI_DOWNLOAD_INTEGRATION === "true";

const hasCookies =
  Boolean(process.env.YT_DLP_COOKIES?.trim()) ||
  Boolean(process.env.YT_DLP_COOKIES_FROM_BROWSER?.trim());

const describeIntegration = RUN ? test : test.skip;

describeIntegration("Bilibili BV1Yx411578x integration", async (t) => {
  if (!hasCookies) {
    t.skip(
      "Set YT_DLP_COOKIES (e.g. secrets/yt-dlp-cookies.txt) for B站 download; see secrets/README.md"
    );
    return;
  }

  const tempDirs = [];
  t.after(() => {
    for (const dir of tempDirs.splice(0)) {
      fs.rmSync(dir, { recursive: true, force: true });
    }
    delete process.env.VIDEO_INGEST_DISABLED;
  });

  await t.test("validateSourceUrl accepts bilibili URL", async () => {
    const sync = validateSourceUrl(BILIBILI_PEPPA_CHONGQING_URL);
    assert.equal(sync.ok, true);
    const asyncResult = await validateSourceUrlAsync(BILIBILI_PEPPA_CHONGQING_URL);
    assert.equal(asyncResult.ok, true);
  });

  await t.test("parseRemoteVideo returns metadata via bilibili view API", async () => {
    delete process.env.VIDEO_INGEST_DISABLED;
    const parsed = await parseRemoteVideo(BILIBILI_PEPPA_CHONGQING_URL, {
      timeoutMs: 60_000,
    });
    assert.equal(parsed.id, BILIBILI_PEPPA_CHONGQING_BVID);
    assert.ok(
      parsed.title?.includes(BILIBILI_PEPPA_CHONGQING_TITLE_PREFIX),
      `unexpected title: ${parsed.title}`
    );
    assert.equal(parsed.duration, BILIBILI_PEPPA_CHONGQING_DURATION_SEC);
    assert.equal(parsed.platform, "bilibili");
  });

  await t.test("downloadRemoteVideo downloads 重庆版小猪佩奇 to mp4", async () => {
    const outputDir = fs.mkdtempSync(path.join(os.tmpdir(), "movieteller_bili_test_"));
    tempDirs.push(outputDir);

    delete process.env.VIDEO_INGEST_DISABLED;

    const result = await downloadRemoteVideo(BILIBILI_PEPPA_CHONGQING_URL, outputDir, {
      timeoutMs: 5 * 60 * 1000,
      maxHeight: 720,
    });

    assert.ok(fs.existsSync(result.path), "downloaded file missing");
    assert.ok(result.size > 1_000_000, `file too small: ${result.size}`);
    assert.equal(result.mimetype, "video/mp4");
    assert.match(result.originalname, /\.mp4$/i);
    assert.ok(
      result.originalname.includes("source") ||
        result.title?.includes(BILIBILI_PEPPA_CHONGQING_TITLE_PREFIX),
      `unexpected download name: ${result.title ?? result.originalname}`
    );
  });
});
