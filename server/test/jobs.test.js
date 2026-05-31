import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import { jobPathsFromRoot } from "../src/config/jobs.js";
import {
  cancelJob,
  clearJobQueueForTests,
  getJobQueueSnapshot,
  markJobRunningForTests,
  markJobWaitingForTests,
  requeueExistingJob,
} from "../src/services/jobs/jobQueue.js";
import {
  markJobCanceledByNode,
  markJobFailed,
  shouldMarkFailedOnRunnerExit,
} from "../src/services/jobs/jobProcess.js";
import { applyRunnerExit, applyRunnerSpawnError } from "../src/services/jobs/runnerExit.js";
import { recoverJobsOnStartup } from "../src/services/jobs/jobRecovery.js";
import { readJobLogs } from "../src/services/jobs/readJobLogs.js";
import {
  listJobArtifacts,
  resolveArtifactDownload,
} from "../src/services/jobs/artifactManifest.js";
import { listJobs } from "../src/services/jobs/listJobs.js";
import { resolveJobThumbnail } from "../src/services/jobs/thumbnail.js";
import {
  removeUploadedTempFile,
  validateJobUploadFile,
} from "../src/services/jobs/uploadValidation.js";

const repoRoot = path.resolve(process.cwd(), "..");
const tempJobRoots = new Set();

function tempJobsRoot() {
  const parent = path.join(repoRoot, "artifacts");
  fs.mkdirSync(parent, { recursive: true });
  const root = fs.mkdtempSync(path.join(parent, "test-jobs-"));
  tempJobRoots.add(root);
  process.env.JOBS_ROOT = root;
  return root;
}

function writeJob(root, jobId, overrides = {}) {
  const jobRoot = path.join(root, jobId);
  const paths = jobPathsFromRoot(jobRoot);
  fs.mkdirSync(paths.logsDir, { recursive: true });
  fs.mkdirSync(path.join(jobRoot, "artifacts"), { recursive: true });
  const record = {
    job_id: jobId,
    status: "queued",
    input_video_path: path.join(jobRoot, "input", "source.mp4"),
    output_root: jobRoot,
    user_id: null,
    current_stage: null,
    progress: {},
    error: null,
    artifacts: {},
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
  fs.writeFileSync(paths.workflowJsonPath, `${JSON.stringify(record, null, 2)}\n`);
  return { jobRoot, paths, record };
}

test.afterEach(() => {
  clearJobQueueForTests();
  for (const root of tempJobRoots) {
    fs.rmSync(root, { recursive: true, force: true });
  }
  tempJobRoots.clear();
  delete process.env.JOBS_ROOT;
  delete process.env.MAX_RUNNING_JOBS;
});

test("canceling a running job requests cancellation without releasing queue slot", () => {
  const root = tempJobsRoot();
  writeJob(root, "running-job", { status: "running" });
  markJobRunningForTests("running-job");

  const result = cancelJob("running-job");

  assert.equal(result.status, "cancel_requested");
  assert.deepEqual(getJobQueueSnapshot().running, ["running-job"]);
  assert.equal(fs.existsSync(path.join(root, "running-job", "cancel.flag")), true);
  const record = JSON.parse(
    fs.readFileSync(path.join(root, "running-job", "workflow.json"), "utf8")
  );
  assert.equal(record.status, "running");
  assert.ok(record.cancel_requested_at);
});

test("canceling a waiting job marks it canceled and removes it from waiting", () => {
  const root = tempJobsRoot();
  const { jobRoot } = writeJob(root, "waiting-job", { status: "queued" });
  markJobWaitingForTests({
    jobId: "waiting-job",
    jobRoot,
    jobsRoot: root,
    videoPath: path.join(jobRoot, "input", "source.mp4"),
    userId: null,
  });

  const result = cancelJob("waiting-job");

  assert.equal(result.status, "canceled");
  assert.deepEqual(getJobQueueSnapshot().waiting, []);
  const record = JSON.parse(fs.readFileSync(path.join(jobRoot, "workflow.json"), "utf8"));
  assert.equal(record.status, "canceled");
});

test("startup recovery fails stale queued and running jobs only", () => {
  const root = tempJobsRoot();
  writeJob(root, "queued-job", { status: "queued" });
  writeJob(root, "running-job", { status: "running" });
  writeJob(root, "done-job", { status: "succeeded" });

  const result = recoverJobsOnStartup({ jobsRoot: root });

  assert.equal(result.scanned, 3);
  assert.equal(result.recovered, 2);
  const queued = JSON.parse(fs.readFileSync(path.join(root, "queued-job", "workflow.json"), "utf8"));
  const running = JSON.parse(fs.readFileSync(path.join(root, "running-job", "workflow.json"), "utf8"));
  const done = JSON.parse(fs.readFileSync(path.join(root, "done-job", "workflow.json"), "utf8"));
  assert.equal(queued.status, "failed");
  assert.equal(queued.error.error_code, "server_restarted");
  assert.equal(running.status, "failed");
  assert.equal(done.status, "succeeded");
});

test("readJobLogs supports limit, malformed lines, and cursor metadata", () => {
  const root = tempJobsRoot();
  const { paths } = writeJob(root, "logs-job");
  const first = `${JSON.stringify({ event: "one" })}\n`;
  const second = `not-json\n`;
  const third = `${JSON.stringify({ event: "three" })}\n`;
  fs.writeFileSync(paths.workflowLogPath, first + second + third);

  const limited = readJobLogs("logs-job", { limit: 2 });
  assert.equal(limited.truncated, true);
  assert.deepEqual(limited.lines, [{ raw: "not-json" }, { event: "three" }]);
  assert.equal(limited.nextOffset, Buffer.byteLength(first + second + third));

  const cursor = readJobLogs("logs-job", { after: Buffer.byteLength(first), limit: 1 });
  assert.deepEqual(cursor.lines, [{ raw: "not-json" }]);
  assert.equal(cursor.truncated, true);
  assert.equal(cursor.nextOffset, Buffer.byteLength(first + second));

  const nextCursor = readJobLogs("logs-job", { after: cursor.nextOffset, limit: 10 });
  assert.deepEqual(nextCursor.lines, [{ event: "three" }]);
  assert.equal(nextCursor.truncated, false);
  assert.equal(nextCursor.nextOffset, Buffer.byteLength(first + second + third));
});

test("listJobs sorts by updated_at desc and paginates", () => {
  const root = tempJobsRoot();
  writeJob(root, "older-job", {
    updated_at: "2026-01-01T00:00:00Z",
    created_at: "2026-01-01T00:00:00Z",
  });
  writeJob(root, "newer-job", {
    updated_at: "2026-01-02T00:00:00Z",
    created_at: "2026-01-02T00:00:00Z",
    status: "running",
    current_stage: "narration",
  });
  fs.mkdirSync(path.join(root, "not-a-job"), { recursive: true });
  fs.writeFileSync(path.join(root, "not-a-job", "readme.txt"), "skip");

  const page = listJobs({ jobsRoot: root, limit: 1, offset: 0 });
  assert.equal(page.total, 2);
  assert.equal(page.limit, 1);
  assert.equal(page.offset, 0);
  assert.equal(page.jobs.length, 1);
  assert.equal(page.jobs[0].jobId, "newer-job");
  assert.equal(page.jobs[0].status, "running");
  assert.equal(page.jobs[0].currentStage, "narration");
  assert.equal(page.jobs[0].inputFileName, "source.mp4");

  const second = listJobs({ jobsRoot: root, limit: 10, offset: 1 });
  assert.equal(second.jobs[0].jobId, "older-job");
});

test("validateJobUploadFile rejects unsupported formats", () => {
  const root = tempJobsRoot();
  const badPath = path.join(root, "bad.txt");
  fs.writeFileSync(badPath, "x");
  const bad = validateJobUploadFile({
    path: badPath,
    originalname: "clip.txt",
    mimetype: "text/plain",
    size: 1,
  });
  assert.equal(bad.ok, false);
  removeUploadedTempFile(badPath);
  assert.equal(fs.existsSync(badPath), false);

  const goodPath = path.join(root, "good.mp4");
  fs.writeFileSync(goodPath, "x");
  const good = validateJobUploadFile({
    path: goodPath,
    originalname: "clip.MP4",
    mimetype: "video/mp4",
    size: 1,
  });
  assert.equal(good.ok, true);
});

test("requeueExistingJob resets failed job to queued and clears cancel flag", () => {
  const root = tempJobsRoot();
  const { jobRoot, paths } = writeJob(root, "retry-job", {
    status: "failed",
    error: { error_code: "provider_timeout", message: "timed out" },
  });
  fs.writeFileSync(paths.cancelFlagPath, "2026-01-01T00:00:00Z\n");
  const videoPath = path.join(jobRoot, "input", "source.mp4");
  fs.mkdirSync(path.dirname(videoPath), { recursive: true });
  fs.writeFileSync(videoPath, "vid");

  const result = requeueExistingJob("retry-job");

  assert.equal(result.status, "queued");
  assert.equal(fs.existsSync(paths.cancelFlagPath), false);
  const record = JSON.parse(fs.readFileSync(paths.workflowJsonPath, "utf8"));
  assert.equal(record.status, "queued");
  assert.equal(record.error, null);
  assert.equal(record.cancel_requested_at, undefined);
});

test("runner exit with cancel flag should mark canceled not failed", () => {
  const root = tempJobsRoot();
  const { jobRoot, paths } = writeJob(root, "cancel-exit-job", { status: "running" });
  fs.writeFileSync(paths.cancelFlagPath, "2026-01-01T00:00:00Z\n");
  assert.equal(shouldMarkFailedOnRunnerExit(jobRoot), true);
  assert.equal(markJobCanceledByNode(jobRoot), true);
  const record = JSON.parse(fs.readFileSync(paths.workflowJsonPath, "utf8"));
  assert.equal(record.status, "canceled");
  assert.equal(record.error, null);
  assert.equal(markJobFailed(jobRoot, { error_code: "runner_exited", message: "x" }), false);
});

test("applyRunnerExit marks canceled when cancel.flag present", () => {
  const root = tempJobsRoot();
  const { jobRoot, paths } = writeJob(root, "exit-cancel-flag", { status: "running" });
  fs.writeFileSync(paths.cancelFlagPath, "2026-01-01T00:00:00Z\n");
  const result = applyRunnerExit(jobRoot, { code: 1, signal: null });
  assert.deepEqual(result, { action: "mark_canceled", reason: "cancel_flag_present", applied: true });
  const record = JSON.parse(fs.readFileSync(paths.workflowJsonPath, "utf8"));
  assert.equal(record.status, "canceled");
  assert.equal(record.error, null);
});

test("applyRunnerExit marks failed on nonzero exit without cancel.flag", () => {
  const root = tempJobsRoot();
  const { jobRoot, paths } = writeJob(root, "exit-failed", { status: "running" });
  const result = applyRunnerExit(jobRoot, { code: 1, signal: null });
  assert.deepEqual(result, { action: "mark_failed", reason: "nonzero_exit", applied: true });
  const record = JSON.parse(fs.readFileSync(paths.workflowJsonPath, "utf8"));
  assert.equal(record.status, "failed");
  assert.equal(record.error?.error_code, "runner_exited");
});

test("applyRunnerExit treats SIGTERM as failed without cancel.flag", () => {
  const root = tempJobsRoot();
  const { jobRoot } = writeJob(root, "exit-sigterm", { status: "running" });
  const result = applyRunnerExit(jobRoot, { code: null, signal: "SIGTERM" });
  assert.equal(result.action, "mark_failed");
  assert.equal(result.applied, true);
});

test("applyRunnerExit no-op on exit 0", () => {
  const root = tempJobsRoot();
  const { jobRoot } = writeJob(root, "exit-zero", { status: "running" });
  const result = applyRunnerExit(jobRoot, { code: 0, signal: null });
  assert.deepEqual(result, { action: "none", reason: "exit_code_0", applied: false });
  const record = JSON.parse(fs.readFileSync(jobPathsFromRoot(jobRoot).workflowJsonPath, "utf8"));
  assert.equal(record.status, "running");
});

test("applyRunnerExit no-op when workflow already terminal", () => {
  const root = tempJobsRoot();
  const { jobRoot, paths } = writeJob(root, "exit-terminal-canceled", {
    status: "canceled",
    error: { error_code: "user_canceled", message: "x" },
  });
  fs.writeFileSync(paths.cancelFlagPath, "2026-01-01T00:00:00Z\n");
  const result = applyRunnerExit(jobRoot, { code: 1, signal: null });
  assert.equal(result.action, "none");
  assert.equal(result.applied, false);
});

test("applyRunnerSpawnError honors cancel.flag", () => {
  const root = tempJobsRoot();
  const { jobRoot, paths } = writeJob(root, "spawn-cancel", { status: "running" });
  fs.writeFileSync(paths.cancelFlagPath, "2026-01-01T00:00:00Z\n");
  const result = applyRunnerSpawnError(jobRoot, { message: "ENOENT python" });
  assert.deepEqual(result, { action: "mark_canceled", reason: "cancel_flag_present", applied: true });
  const record = JSON.parse(fs.readFileSync(paths.workflowJsonPath, "utf8"));
  assert.equal(record.status, "canceled");
});

test("requeueExistingJob rejects non-terminal status", () => {
  const root = tempJobsRoot();
  writeJob(root, "running-job", { status: "running" });
  assert.throws(() => requeueExistingJob("running-job"), /cannot retry/);
});

test("artifact manifest wins over legacy artifacts and rejects traversal", () => {
  const root = tempJobsRoot();
  const { jobRoot, paths } = writeJob(root, "artifact-job", {
    status: "succeeded",
    artifacts: {
      renderedVideoPath: path.join(root, "artifact-job", "legacy.mp4"),
    },
  });
  const artifactPath = path.join(jobRoot, "artifacts", "narrated.mp4");
  fs.writeFileSync(artifactPath, "video");
  fs.writeFileSync(paths.artifactManifestPath, JSON.stringify([
    {
      kind: "renderedVideo",
      label: "Rendered video",
      path: artifactPath,
      mediaType: "video/mp4",
    },
  ]));

  const artifacts = listJobArtifacts("artifact-job");
  assert.equal(artifacts.length, 1);
  assert.equal(artifacts[0].kind, "renderedVideo");
  assert.equal(resolveArtifactDownload("artifact-job", "renderedVideo").filePath, artifactPath);

  assert.throws(
    () => resolveArtifactDownload("artifact-job", "sourceVideo"),
    /unknown artifact kind/
  );

  fs.writeFileSync(paths.artifactManifestPath, JSON.stringify([
    {
      kind: "renderedVideo",
      label: "Bad",
      path: path.join(os.tmpdir(), "outside.mp4"),
    },
  ]));
  assert.throws(
    () => resolveArtifactDownload("artifact-job", "renderedVideo"),
    /artifact path not allowed/
  );
});

test("resolveJobThumbnail serves first frame-pool image and rejects traversal", () => {
  const root = tempJobsRoot();
  const { jobRoot } = writeJob(root, "thumb-job", { status: "succeeded" });
  const framePool = path.join(jobRoot, "frame_pool");
  const imageDir = path.join(framePool, "images");
  fs.mkdirSync(imageDir, { recursive: true });
  const imagePath = path.join(imageDir, "000001.png");
  fs.writeFileSync(imagePath, "png");
  fs.writeFileSync(
    path.join(framePool, "manifest.jsonl"),
    `${JSON.stringify({
      schemaVersion: 1,
      shotId: 0,
      tSec: 0.1,
      imageRef: "images/000001.png",
      embeddingIndex: null,
    })}\n`
  );

  assert.equal(resolveJobThumbnail("thumb-job").filePath, imagePath);

  fs.writeFileSync(
    path.join(framePool, "manifest.jsonl"),
    `${JSON.stringify({
      schemaVersion: 1,
      shotId: 0,
      tSec: 0.1,
      imageRef: "../outside.png",
      embeddingIndex: null,
    })}\n`
  );
  assert.throws(() => resolveJobThumbnail("thumb-job"), /thumbnail path not allowed/);
});

test("list jobs resolve display title from request.json when workflow lacks original_source", () => {
  const root = tempJobsRoot();
  const { jobRoot, paths } = writeJob(root, "title-job", {
    status: "succeeded",
  });
  fs.writeFileSync(
    paths.requestJsonPath,
    `${JSON.stringify(
      { enableSpeech: true, originalFilename: "my-lecture.mp4" },
      null,
      2
    )}\n`
  );

  const listed = listJobs({ jobsRoot: root, limit: 10 }).jobs.find(
    (job) => job.jobId === "title-job"
  );
  assert.ok(listed);
  assert.equal(listed.originalSource?.original_filename, "my-lecture.mp4");
  assert.equal(listed.inputFileName, "source.mp4");
});

test("jobs without enableSpeech omit rendered video from list API and artifacts", () => {
  const root = tempJobsRoot();
  const { jobRoot, paths } = writeJob(root, "no-speech-job", {
    status: "succeeded",
  });
  fs.writeFileSync(
    paths.requestJsonPath,
    `${JSON.stringify({ enableSpeech: false, enableEmbedVideo: true }, null, 2)}\n`
  );
  const artifactPath = path.join(jobRoot, "render", "narrated.mp4");
  fs.mkdirSync(path.dirname(artifactPath), { recursive: true });
  fs.writeFileSync(artifactPath, "video");
  fs.writeFileSync(
    paths.artifactManifestPath,
    JSON.stringify([
      {
        kind: "renderedVideo",
        label: "Rendered video",
        path: artifactPath,
        mediaType: "video/mp4",
      },
      {
        kind: "studyCardsHtml",
        label: "Study cards",
        path: path.join(jobRoot, "study_cards", "study_cards.html"),
        mediaType: "text/html",
      },
    ])
  );
  fs.mkdirSync(path.join(jobRoot, "study_cards"), { recursive: true });
  fs.writeFileSync(path.join(jobRoot, "study_cards", "study_cards.html"), "<html></html>");

  const listed = listJobs({ jobsRoot: root, limit: 10 }).jobs.find(
    (job) => job.jobId === "no-speech-job"
  );
  assert.ok(listed);
  assert.equal(listed.enableSpeech, false);

  const artifacts = listJobArtifacts("no-speech-job");
  assert.ok(artifacts.every((item) => item.kind !== "renderedVideo"));
  assert.throws(
    () => resolveArtifactDownload("no-speech-job", "renderedVideo"),
    /artifact not available/
  );
});
