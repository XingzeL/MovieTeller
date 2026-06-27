import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import { VideoDownloadError } from "../src/services/billing/errors.js";
import {
  downloadRemoteVideo,
  parseYtDlpDurationFromStdout,
} from "../src/services/media/downloadRemoteVideo.js";

process.env.VIDEO_INGEST_DISABLED = "1";

const tempDirs = [];

function tempOutputDir() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "movieteller_dl_test_"));
  tempDirs.push(dir);
  return dir;
}

/**
 * @param {{ stdout?: string, stderr?: string, code?: number }} behavior
 */
function fakeSpawn(behavior) {
  return (_cmd, _args, _opts) => {
    const child = new EventEmitter();
    child.stdout = new EventEmitter();
    child.stderr = new EventEmitter();
    child.kill = () => {};
    queueMicrotask(() => {
      if (behavior.stdout) child.stdout.emit("data", behavior.stdout);
      if (behavior.stderr) child.stderr.emit("data", behavior.stderr);
      child.emit("close", behavior.code ?? 0);
    });
    return child;
  };
}

test.afterEach(() => {
  for (const dir of tempDirs.splice(0)) {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("downloadRemoteVideo returns file metadata on success", async () => {
  const outputDir = tempOutputDir();
  const videoPath = path.join(outputDir, "source.mp4");
  fs.writeFileSync(videoPath, Buffer.alloc(1024));

  const result = await downloadRemoteVideo("https://example.com/watch", outputDir, {
    ytDlpPath: "yt-dlp",
    timeoutMs: 5_000,
    title: "Sample Title",
    spawnFn: fakeSpawn({ stdout: "[download] done\nduration:123.4\n" }),
  });

  assert.equal(result.path, videoPath);
  assert.equal(result.size, 1024);
  assert.equal(result.mimetype, "video/mp4");
  assert.match(result.originalname, /Sample Title\.mp4$/);
  assert.equal(result.title, "Sample Title");
  assert.equal(result.durationSec, 123.4);
});

test("parseYtDlpDurationFromStdout returns last valid duration marker", () => {
  assert.equal(parseYtDlpDurationFromStdout("duration:0\nduration:65.2\n"), 65.2);
  assert.equal(parseYtDlpDurationFromStdout("duration:NA\n"), null);
  assert.equal(parseYtDlpDurationFromStdout(""), null);
});

test("downloadRemoteVideo throws VideoDownloadError when yt-dlp fails", async () => {
  const outputDir = tempOutputDir();
  await assert.rejects(
    () =>
      downloadRemoteVideo("https://example.com/watch", outputDir, {
        timeoutMs: 5_000,
        spawnFn: fakeSpawn({ stderr: "ERROR: unavailable", code: 1 }),
      }),
    (err) => {
      assert.ok(err instanceof VideoDownloadError);
      assert.equal(err.code, "video_download_failed");
      assert.match(String(err.message), /yt-dlp failed/);
      return true;
    }
  );
});

test("downloadRemoteVideo rejects files over maxBytes", async () => {
  const outputDir = tempOutputDir();
  const videoPath = path.join(outputDir, "source.mp4");
  fs.writeFileSync(videoPath, Buffer.alloc(2048));

  await assert.rejects(
    () =>
      downloadRemoteVideo("https://example.com/watch", outputDir, {
        maxBytes: 1024,
        timeoutMs: 5_000,
        spawnFn: fakeSpawn({ stdout: "" }),
      }),
    (err) => {
      assert.ok(err instanceof VideoDownloadError);
      assert.match(String(err.message), /exceeds size limit/);
      assert.equal(fs.existsSync(videoPath), false);
      return true;
    }
  );
});
