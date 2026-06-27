import assert from "node:assert/strict";
import test from "node:test";

import {
  extractSourceUrlFromBody,
  validateSourceUrl,
} from "../src/services/media/validateSourceUrl.js";

test("extractSourceUrlFromBody prefers sourceUrl and accepts aliases", () => {
  assert.equal(
    extractSourceUrlFromBody({ sourceUrl: " https://example.com/a " }),
    "https://example.com/a"
  );
  assert.equal(
    extractSourceUrlFromBody({ youtubeUrl: "https://youtu.be/abc" }),
    "https://youtu.be/abc"
  );
  assert.equal(extractSourceUrlFromBody({}), null);
});

test("validateSourceUrl accepts public https URLs", () => {
  const prev = process.env.SOURCE_URL_ALLOWLIST;
  process.env.SOURCE_URL_ALLOWLIST = "example.com,bilibili.com";
  try {
    const result = validateSourceUrl("https://www.bilibili.com/video/BV1Yx411578x");
    assert.equal(result.ok, true);
    if (result.ok) {
      assert.equal(result.url, "https://www.bilibili.com/video/BV1Yx411578x");
    }
  } finally {
    if (prev === undefined) delete process.env.SOURCE_URL_ALLOWLIST;
    else process.env.SOURCE_URL_ALLOWLIST = prev;
  }
});

test("validateSourceUrl rejects YouTube while channel is disabled", () => {
  const prev = process.env.SOURCE_URL_ALLOWLIST;
  process.env.SOURCE_URL_ALLOWLIST = "youtube.com,youtu.be,bilibili.com";
  try {
    for (const url of [
      "https://www.youtube.com/watch?v=abc",
      "https://youtu.be/abc",
      "https://m.youtube.com/watch?v=abc",
    ]) {
      const result = validateSourceUrl(url);
      assert.equal(result.ok, false);
      if (!result.ok) {
        assert.equal(result.message, "暂不支持 YouTube 链接，请改用本地 MP4 上传。");
      }
    }
  } finally {
    if (prev === undefined) delete process.env.SOURCE_URL_ALLOWLIST;
    else process.env.SOURCE_URL_ALLOWLIST = prev;
  }
});

test("validateSourceUrl rejects hosts outside allowlist", () => {
  const prev = process.env.SOURCE_URL_ALLOWLIST;
  process.env.SOURCE_URL_ALLOWLIST = "bilibili.com";
  try {
    const result = validateSourceUrl("https://example.com/video");
    assert.equal(result.ok, false);
  } finally {
    if (prev === undefined) delete process.env.SOURCE_URL_ALLOWLIST;
    else process.env.SOURCE_URL_ALLOWLIST = prev;
  }
});

test("validateSourceUrl rejects missing and invalid URLs", () => {
  assert.deepEqual(validateSourceUrl(""), { ok: false, message: "sourceUrl is required" });
  assert.deepEqual(validateSourceUrl("not-a-url"), {
    ok: false,
    message: "sourceUrl must be a valid URL",
  });
  assert.deepEqual(validateSourceUrl("ftp://example.com/v.mp4"), {
    ok: false,
    message: "sourceUrl must use http or https",
  });
});

test("validateSourceUrl blocks localhost and private networks", () => {
  for (const url of [
    "http://localhost/video",
    "http://127.0.0.1/video",
    "http://10.0.0.5/video",
    "http://192.168.1.2/video",
    "http://172.16.0.1/video",
  ]) {
    const result = validateSourceUrl(url);
    assert.equal(result.ok, false);
    if (!result.ok) {
      assert.equal(result.message, "sourceUrl points to a blocked host");
    }
  }
});
