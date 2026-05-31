import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

import { clearJobQueueForTests } from "../src/services/jobs/jobQueue.js";
import { enqueueJobUpload } from "../src/services/jobs/jobQueue.js";
import { createApp } from "../src/app.js";
import { jobPathsFromRoot } from "../src/config/jobs.js";
import { tickOnce } from "../src/runtime/queueWorker.js";
import { recoverForCombined } from "../src/runtime/startupRecovery.js";
import { startTestServer } from "./testServer.js";

const repoRoot = path.resolve(process.cwd(), "..");

/**
 * @param {string} root
 * @param {string} jobId
 */
function writeQueuedJob(root, jobId) {
  const jobRoot = path.join(root, jobId);
  const paths = jobPathsFromRoot(jobRoot);
  fs.mkdirSync(paths.inputDir, { recursive: true });
  const videoPath = path.join(paths.inputDir, "source.mp4");
  fs.writeFileSync(videoPath, "fake");
  fs.writeFileSync(
    paths.workflowJsonPath,
    `${JSON.stringify(
      {
        job_id: jobId,
        status: "queued",
        user_id: "user-a",
        input_video_path: videoPath,
        output_root: jobRoot,
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      },
      null,
      2
    )}\n`
  );
  fs.writeFileSync(
    paths.requestJsonPath,
    `${JSON.stringify({ enableSpeech: false }, null, 2)}\n`
  );
  return { jobRoot, paths, videoPath };
}

test("api run mode leaves job queued without runner.pid", async (t) => {
  const root = fs.mkdtempSync(path.join(repoRoot, "artifacts", "test-worker-"));
  const prevMode = process.env.MOVIE_TELLER_RUN_MODE;
  process.env.JOBS_ROOT = root;
  process.env.MOVIE_TELLER_RUN_MODE = "api";
  clearJobQueueForTests();

  const app = createApp({ includeDevRoutes: true });
  const { baseUrl, close } = await startTestServer(app);
  t.after(async () => {
    await close();
    fs.rmSync(root, { recursive: true, force: true });
    delete process.env.JOBS_ROOT;
    clearJobQueueForTests();
    if (prevMode === undefined) delete process.env.MOVIE_TELLER_RUN_MODE;
    else process.env.MOVIE_TELLER_RUN_MODE = prevMode;
  });

  const videoPath = path.join(root, "_upload.mp4");
  fs.writeFileSync(videoPath, "x".repeat(128));
  const form = new FormData();
  form.append("file", new Blob([fs.readFileSync(videoPath)]), "clip.mp4");
  form.append("enableSpeech", "false");

  const res = await fetch(`${baseUrl}/api/jobs`, {
    method: "POST",
    headers: { Cookie: "mt_uid=user-a" },
    body: form,
  });
  assert.equal(res.status, 201);
  const body = await res.json();
  const paths = jobPathsFromRoot(path.join(root, body.jobId));
  const workflow = JSON.parse(fs.readFileSync(paths.workflowJsonPath, "utf8"));
  assert.equal(workflow.status, "queued");
  assert.equal(fs.existsSync(paths.runnerPidPath), false);
});

test("api recovery does not fail queued jobs on disk", () => {
  const root = fs.mkdtempSync(path.join(repoRoot, "artifacts", "test-worker-"));
  const prevMode = process.env.MOVIE_TELLER_RUN_MODE;
  process.env.JOBS_ROOT = root;
  process.env.MOVIE_TELLER_RUN_MODE = "api";

  writeQueuedJob(root, "stay-queued");
  const result = recoverForCombined({ jobsRoot: root });
  assert.equal(result.skipped, true);
  const workflow = JSON.parse(
    fs.readFileSync(path.join(root, "stay-queued", "workflow.json"), "utf8")
  );
  assert.equal(workflow.status, "queued");

  fs.rmSync(root, { recursive: true, force: true });
  delete process.env.JOBS_ROOT;
  if (prevMode === undefined) delete process.env.MOVIE_TELLER_RUN_MODE;
  else process.env.MOVIE_TELLER_RUN_MODE = prevMode;
});

test("worker tickOnce picks a queued job", async (t) => {
  const root = fs.mkdtempSync(path.join(repoRoot, "artifacts", "test-worker-"));
  const prevMode = process.env.MOVIE_TELLER_RUN_MODE;
  process.env.JOBS_ROOT = root;
  process.env.MOVIE_TELLER_RUN_MODE = "worker";
  clearJobQueueForTests();

  const { paths } = writeQueuedJob(root, "pick-me");
  t.after(() => {
    fs.rmSync(root, { recursive: true, force: true });
    delete process.env.JOBS_ROOT;
    clearJobQueueForTests();
    if (prevMode === undefined) delete process.env.MOVIE_TELLER_RUN_MODE;
    else process.env.MOVIE_TELLER_RUN_MODE = prevMode;
  });

  const result = tickOnce({ jobsRoot: root });
  assert.ok(result.picked >= 1);
  assert.equal(fs.existsSync(paths.workerLockPath), true);
});
