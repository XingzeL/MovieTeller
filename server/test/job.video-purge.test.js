import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

import { clearJobQueueForTests } from "../src/services/jobs/jobQueue.js";
import { createApp } from "../src/app.js";
import { jobPathsFromRoot } from "../src/config/jobs.js";
import { startTestServer } from "./testServer.js";

const repoRoot = path.resolve(process.cwd(), "..");

/**
 * @param {string} root
 * @param {string} jobId
 */
function writeJobFixture(root, jobId) {
  const jobRoot = path.join(root, jobId);
  const paths = jobPathsFromRoot(jobRoot);
  fs.mkdirSync(paths.inputDir, { recursive: true });
  fs.mkdirSync(paths.logsDir, { recursive: true });
  fs.mkdirSync(path.join(jobRoot, "study_cards"), { recursive: true });
  fs.mkdirSync(path.join(jobRoot, "render"), { recursive: true });
  const studyPath = path.join(jobRoot, "study_cards", "study_cards.html");
  const videoPath = path.join(jobRoot, "render", "narrated.mp4");
  fs.writeFileSync(studyPath, "<html><body>study</body></html>");
  fs.writeFileSync(videoPath, "video-bytes");
  const record = {
    job_id: jobId,
    status: "succeeded",
    user_id: "user-a",
    input_video_path: path.join(paths.inputDir, "source.mp4"),
    output_root: jobRoot,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    artifacts: {},
  };
  fs.writeFileSync(paths.workflowJsonPath, `${JSON.stringify(record, null, 2)}\n`);
  fs.mkdirSync(path.dirname(paths.artifactManifestPath), { recursive: true });
  fs.writeFileSync(
    paths.artifactManifestPath,
    `${JSON.stringify(
      [
        {
          kind: "renderedVideo",
          label: "Rendered video",
          path: videoPath,
          mediaType: "video/mp4",
        },
        {
          kind: "studyCardsHtml",
          label: "Study cards",
          path: studyPath,
          mediaType: "text/html",
        },
      ],
      null,
      2
    )}\n`
  );
  fs.writeFileSync(
    path.join(jobRoot, "request.json"),
    `${JSON.stringify({ enableSpeech: true }, null, 2)}\n`
  );
  return { jobRoot, paths, studyPath, videoPath };
}

/**
 * @param {string} baseUrl
 * @param {string} cookie
 * @param {string} reqPath
 */
async function fetchAsUser(baseUrl, cookie, reqPath) {
  return fetch(`${baseUrl}${reqPath}`, {
    headers: { Cookie: cookie },
  });
}

/**
 * @param {() => boolean} predicate
 * @param {{ timeoutMs?: number, intervalMs?: number }} [opts]
 */
async function waitUntil(predicate, opts = {}) {
  const timeoutMs = opts.timeoutMs ?? 2000;
  const intervalMs = opts.intervalMs ?? 50;
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    if (predicate()) return;
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  throw new Error("waitUntil timed out");
}

test("after video download purge keeps study cards and blocks repeat download (§ Video policy)", async (t) => {
  const root = fs.mkdtempSync(path.join(repoRoot, "artifacts", "test-jobs-"));
  process.env.JOBS_ROOT = root;
  clearJobQueueForTests();

  const jobId = "purge-after-download";
  const { paths, videoPath } = writeJobFixture(root, jobId);

  const app = createApp({ includeDevRoutes: true });
  const { baseUrl, close } = await startTestServer(app);
  t.after(async () => {
    await close();
    fs.rmSync(root, { recursive: true, force: true });
    delete process.env.JOBS_ROOT;
    clearJobQueueForTests();
  });

  const download = await fetchAsUser(
    baseUrl,
    "mt_uid=user-a",
    `/api/jobs/${jobId}/artifacts/renderedVideo`
  );
  assert.equal(download.status, 200);
  await download.arrayBuffer();

  await waitUntil(() => {
    const wf = JSON.parse(fs.readFileSync(paths.workflowJsonPath, "utf8"));
    return Boolean(wf.video_purged_at) || !fs.existsSync(videoPath);
  });

  const workflow = JSON.parse(fs.readFileSync(paths.workflowJsonPath, "utf8"));
  assert.ok(workflow.video_downloaded_at);
  assert.ok(workflow.video_purged_at);
  assert.equal(fs.existsSync(videoPath), false);

  const studyInline = await fetchAsUser(
    baseUrl,
    "mt_uid=user-a",
    `/api/jobs/${jobId}/artifacts/studyCardsHtml?inline=1`
  );
  assert.equal(studyInline.status, 200);

  const again = await fetchAsUser(
    baseUrl,
    "mt_uid=user-a",
    `/api/jobs/${jobId}/artifacts/renderedVideo`
  );
  assert.equal(again.status, 410);
});
