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
  const result = validateSourceUrl("https://www.youtube.com/watch?v=abc");
  assert.equal(result.ok, true);
  if (result.ok) {
    assert.equal(result.url, "https://www.youtube.com/watch?v=abc");
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
