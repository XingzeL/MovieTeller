import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import test from "node:test";

import { VideoParseError } from "../src/services/billing/errors.js";
import { parseRemoteVideo } from "../src/services/media/parseRemoteVideo.js";

/**
 * @param {{ stdout?: string, code?: number }} behavior
 */
function fakeSpawn(behavior) {
  return (_cmd, _args, _opts) => {
    const child = new EventEmitter();
    child.stdout = new EventEmitter();
    child.stderr = new EventEmitter();
    child.kill = () => {};
    queueMicrotask(() => {
      if (behavior.stdout) child.stdout.emit("data", behavior.stdout);
      child.emit("close", behavior.code ?? 0);
    });
    return child;
  };
}

test("parseRemoteVideo returns normalized metadata", async () => {
  process.env.VIDEO_INGEST_DISABLED = "1";
  const payload = JSON.stringify({
    id: "abc",
    title: "Sample",
    duration: 125,
    extractor: "youtube",
    thumbnail: "https://example.com/t.jpg",
    uploader: "Channel",
  });
  const result = await parseRemoteVideo("https://www.youtube.com/watch?v=abc", {
    preferIngest: false,
    spawnFn: fakeSpawn({ stdout: payload }),
  });
  assert.equal(result.title, "Sample");
  assert.equal(result.duration, 125);
  assert.equal(result.platform, "youtube");
  delete process.env.VIDEO_INGEST_DISABLED;
});

test("parseRemoteVideo throws VideoParseError on failure", async () => {
  process.env.VIDEO_INGEST_DISABLED = "1";
  await assert.rejects(
    () =>
      parseRemoteVideo("https://www.youtube.com/watch?v=abc", {
        preferIngest: false,
        spawnFn: fakeSpawn({ code: 1 }),
      }),
    (err) => {
      assert.ok(err instanceof VideoParseError);
      return true;
    }
  );
  delete process.env.VIDEO_INGEST_DISABLED;
});
