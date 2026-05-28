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
} from "../src/services/jobs/jobQueue.js";
import { recoverJobsOnStartup } from "../src/services/jobs/jobRecovery.js";
import { readJobLogs } from "../src/services/jobs/readJobLogs.js";
import {
  listJobArtifacts,
  resolveArtifactDownload,
} from "../src/services/jobs/artifactManifest.js";

const repoRoot = path.resolve(process.cwd(), "..");

function tempJobsRoot() {
  const parent = path.join(repoRoot, "artifacts");
  fs.mkdirSync(parent, { recursive: true });
  const root = fs.mkdtempSync(path.join(parent, "test-jobs-"));
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

  fs.writeFileSync(paths.artifactManifestPath, JSON.stringify([
    { kind: "bad", label: "Bad", path: path.join(os.tmpdir(), "outside.mp4") },
  ]));
  assert.throws(() => resolveArtifactDownload("artifact-job", "bad"), /artifact path not allowed/);
});
