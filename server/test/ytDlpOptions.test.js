import assert from "node:assert/strict";
import test from "node:test";

import {
  buildYtDlpExtraArgs,
  resolveYtDlpCookiesPath,
  summarizeYtDlpFailure,
} from "../src/services/media/ytDlpOptions.js";

test("buildYtDlpExtraArgs prefers cookies file over browser", () => {
  const args = buildYtDlpExtraArgs({
    yt_dlp_cookies_from_browser: "chrome",
    yt_dlp_cookies: "/tmp/cookies.txt",
    yt_dlp_impersonate: "chrome",
  });
  assert.deepEqual(args, ["--cookies", "/tmp/cookies.txt", "--impersonate", "chrome"]);
});

test("buildYtDlpExtraArgs uses browser cookies when file unset", () => {
  const args = buildYtDlpExtraArgs({
    yt_dlp_cookies_from_browser: "chrome",
    yt_dlp_impersonate: "chrome",
  });
  assert.deepEqual(args, [
    "--cookies-from-browser",
    "chrome",
    "--impersonate",
    "chrome",
  ]);
});

test("resolveYtDlpCookiesPath resolves relative paths from repo root", () => {
  const resolved = resolveYtDlpCookiesPath("secrets/yt-dlp-cookies.txt");
  assert.match(resolved, /secrets[/\\]yt-dlp-cookies\.txt$/);
});

test("buildYtDlpExtraArgs adds bilibili referer", () => {
  const args = buildYtDlpExtraArgs({}, "https://www.bilibili.com/video/BV1Yx411578x");
  assert.deepEqual(args, ["--add-header", "Referer:https://www.bilibili.com/"]);
});

test("summarizeYtDlpFailure maps YouTube bot check", () => {
  const msg = summarizeYtDlpFailure(
    "yt-dlp failed (1): ERROR: Sign in to confirm you're not a bot"
  );
  assert.match(msg, /YouTube/);
  assert.match(msg, /YT_DLP_COOKIES/);
});

test("summarizeYtDlpFailure maps Bilibili 412", () => {
  const msg = summarizeYtDlpFailure(
    "yt-dlp failed (1): ERROR: [BiliBili] xxx: HTTP Error 412: Precondition Failed"
  );
  assert.match(msg, /B/);
});
