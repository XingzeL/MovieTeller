import assert from "node:assert/strict";
import test from "node:test";

import { buildYtDlpFormatSelector } from "../src/services/media/buildYtDlpFormat.js";

test("buildYtDlpFormatSelector caps height", () => {
  const prev = process.env.YT_DLP_MAX_HEIGHT;
  process.env.YT_DLP_MAX_HEIGHT = "480";
  try {
    assert.equal(
      buildYtDlpFormatSelector(),
      "bestvideo[height<=480]+bestaudio/best[height<=480]/best"
    );
  } finally {
    if (prev === undefined) delete process.env.YT_DLP_MAX_HEIGHT;
    else process.env.YT_DLP_MAX_HEIGHT = prev;
  }
});
