import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

import { jobPathsFromRoot } from "../src/config/jobs.js";
import {
  claimAndSpawn,
  releaseClaim,
  releaseClaimIfOwned,
  tryClaim,
} from "../src/services/jobs/claimJob.js";
import {
  clearJobQueueForTests,
  getJobQueueSnapshot,
  releaseQueueSlotAndClaim,
  releaseQueueSlotOnly,
  tryAcquireQueueSlot,
} from "../src/services/jobs/jobQueue.js";

const repoRoot = path.resolve(process.cwd(), "..");

test("tryClaim allows only one concurrent claim", () => {
  const root = fs.mkdtempSync(path.join(repoRoot, "artifacts", "test-claim-"));
  const jobRoot = path.join(root, "job-1");
  fs.mkdirSync(jobRoot, { recursive: true });
  fs.writeFileSync(
    path.join(jobRoot, "workflow.json"),
    `${JSON.stringify({ job_id: "job-1", status: "queued" }, null, 2)}\n`
  );

  assert.equal(tryClaim("job-1", jobRoot), true);
  assert.equal(tryClaim("job-1", jobRoot), false);
  releaseClaim(jobRoot);
  assert.equal(tryClaim("job-1", jobRoot), true);
  releaseClaim(jobRoot);
  fs.rmSync(root, { recursive: true, force: true });
});

test("stale lock with dead pid can be stolen", () => {
  const root = fs.mkdtempSync(path.join(repoRoot, "artifacts", "test-claim-"));
  const jobRoot = path.join(root, "job-stale");
  fs.mkdirSync(jobRoot, { recursive: true });
  const paths = jobPathsFromRoot(jobRoot);
  fs.writeFileSync(
    paths.workflowJsonPath,
    `${JSON.stringify({ job_id: "job-stale", status: "queued" }, null, 2)}\n`
  );
  fs.writeFileSync(
    paths.workerLockPath,
    `${JSON.stringify({ pid: 999999999, claimedAt: new Date().toISOString() })}\n`
  );

  assert.equal(tryClaim("job-stale", jobRoot), true);
  releaseClaim(jobRoot);
  fs.rmSync(root, { recursive: true, force: true });
});

test("claimAndSpawn releases lock when spawn fails", () => {
  const root = fs.mkdtempSync(path.join(repoRoot, "artifacts", "test-claim-"));
  const jobId = "job-spawn-fail";
  const jobRoot = path.join(root, jobId);
  fs.mkdirSync(jobRoot, { recursive: true });
  const paths = jobPathsFromRoot(jobRoot);
  fs.writeFileSync(
    paths.workflowJsonPath,
    `${JSON.stringify({ job_id: jobId, status: "queued" }, null, 2)}\n`
  );

  const prev = process.env.MOVIE_TELLER_RUN_MODE;
  process.env.MOVIE_TELLER_RUN_MODE = "api";
  try {
    assert.throws(
      () =>
        claimAndSpawn({
          jobId,
          jobRoot,
          jobsRoot: root,
          videoPath: path.join(jobRoot, "missing.mp4"),
          userId: "user-a",
        }),
      /spawn is disabled/
    );
  } finally {
    if (prev === undefined) delete process.env.MOVIE_TELLER_RUN_MODE;
    else process.env.MOVIE_TELLER_RUN_MODE = prev;
  }

  assert.equal(fs.existsSync(paths.workerLockPath), false);
  fs.rmSync(root, { recursive: true, force: true });
});

test("releaseClaimIfOwned does not remove another process lock", () => {
  const root = fs.mkdtempSync(path.join(repoRoot, "artifacts", "test-claim-"));
  const jobRoot = path.join(root, "job-other-lock");
  fs.mkdirSync(jobRoot, { recursive: true });
  const paths = jobPathsFromRoot(jobRoot);
  fs.writeFileSync(
    paths.workerLockPath,
    `${JSON.stringify({ pid: 1, claimedAt: new Date().toISOString() })}\n`
  );

  releaseClaimIfOwned(jobRoot);
  assert.ok(fs.existsSync(paths.workerLockPath));
  const payload = JSON.parse(fs.readFileSync(paths.workerLockPath, "utf8"));
  assert.equal(payload.pid, 1);

  fs.rmSync(root, { recursive: true, force: true });
});

test("stale lock with alive pid and old claimedAt on queued job can be stolen", () => {
  let otherPid = 1;
  try {
    process.kill(otherPid, 0);
  } catch {
    return; // init not signalable on this platform
  }

  const root = fs.mkdtempSync(path.join(repoRoot, "artifacts", "test-claim-"));
  const jobRoot = path.join(root, "job-stale-time");
  fs.mkdirSync(jobRoot, { recursive: true });
  const paths = jobPathsFromRoot(jobRoot);
  const oldClaimedAt = new Date(Date.now() - 31 * 60 * 1000).toISOString();
  fs.writeFileSync(
    paths.workflowJsonPath,
    `${JSON.stringify({ job_id: "job-stale-time", status: "queued" }, null, 2)}\n`
  );
  fs.writeFileSync(
    paths.workerLockPath,
    `${JSON.stringify({ pid: otherPid, claimedAt: oldClaimedAt })}\n`
  );

  assert.equal(tryClaim("job-stale-time", jobRoot), true);
  releaseClaim(jobRoot);
  fs.rmSync(root, { recursive: true, force: true });
});

test("failed claim after slot acquire keeps foreign lock and frees slot", () => {
  let otherPid = 1;
  try {
    process.kill(otherPid, 0);
  } catch {
    return;
  }

  const root = fs.mkdtempSync(path.join(repoRoot, "artifacts", "test-claim-"));
  const jobId = "job-foreign-lock";
  const jobRoot = path.join(root, jobId);
  fs.mkdirSync(jobRoot, { recursive: true });
  const paths = jobPathsFromRoot(jobRoot);
  fs.mkdirSync(paths.inputDir, { recursive: true });
  const videoPath = path.join(paths.inputDir, "source.mp4");
  fs.writeFileSync(videoPath, "x");
  fs.writeFileSync(
    paths.workflowJsonPath,
    `${JSON.stringify(
      {
        job_id: jobId,
        status: "queued",
        input_video_path: videoPath,
        output_root: jobRoot,
      },
      null,
      2
    )}\n`
  );
  fs.writeFileSync(
    paths.workerLockPath,
    `${JSON.stringify({ pid: otherPid, claimedAt: new Date().toISOString() })}\n`
  );

  clearJobQueueForTests();
  const prev = process.env.MOVIE_TELLER_RUN_MODE;
  process.env.MOVIE_TELLER_RUN_MODE = "worker";

  const prepared = {
    jobId,
    jobRoot,
    jobsRoot: root,
    videoPath,
    userId: "user-a",
  };

  try {
    assert.equal(tryAcquireQueueSlot(prepared), true);
    assert.equal(claimAndSpawn(prepared), false);
    releaseQueueSlotOnly(jobId);

    assert.ok(fs.existsSync(paths.workerLockPath));
    assert.equal(JSON.parse(fs.readFileSync(paths.workerLockPath, "utf8")).pid, otherPid);
    assert.equal(getJobQueueSnapshot().running.length, 0);
  } finally {
    clearJobQueueForTests();
    if (prev === undefined) delete process.env.MOVIE_TELLER_RUN_MODE;
    else process.env.MOVIE_TELLER_RUN_MODE = prev;
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test("spawn error after slot acquire releases slot and owned lock", () => {
  const root = fs.mkdtempSync(path.join(repoRoot, "artifacts", "test-claim-"));
  const jobId = "job-slot-leak";
  const jobRoot = path.join(root, jobId);
  fs.mkdirSync(jobRoot, { recursive: true });
  const paths = jobPathsFromRoot(jobRoot);
  fs.writeFileSync(
    paths.workflowJsonPath,
    `${JSON.stringify({ job_id: jobId, status: "queued" }, null, 2)}\n`
  );

  clearJobQueueForTests();
  const prev = process.env.MOVIE_TELLER_RUN_MODE;
  process.env.MOVIE_TELLER_RUN_MODE = "api";

  const prepared = {
    jobId,
    jobRoot,
    jobsRoot: root,
    videoPath: path.join(jobRoot, "missing.mp4"),
    userId: "user-a",
  };

  try {
    assert.equal(tryAcquireQueueSlot(prepared), true);
    assert.throws(() => claimAndSpawn(prepared), /spawn is disabled/);
    releaseQueueSlotAndClaim(jobId, jobRoot);
    assert.equal(getJobQueueSnapshot().running.length, 0);
    assert.equal(fs.existsSync(paths.workerLockPath), false);
  } finally {
    clearJobQueueForTests();
    if (prev === undefined) delete process.env.MOVIE_TELLER_RUN_MODE;
    else process.env.MOVIE_TELLER_RUN_MODE = prev;
    fs.rmSync(root, { recursive: true, force: true });
  }
});
