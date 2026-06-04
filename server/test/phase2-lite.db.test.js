import assert from "node:assert/strict";
import crypto from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import { closePool } from "../src/db/pool.js";
import { runMigrations } from "../src/db/ensure.js";
import {
  failJobByWorker,
  getJobById,
  insertJobQueued,
  markJobCanceling,
  markJobCanceledQueued,
  markJobForcedCanceledByWorker,
  reconcileJobFromWorkflow,
  retryJobInDb,
  syncVideoStateToDb,
} from "../src/db/jobsRepository.js";
import { ensureCancelFlagForDbJob } from "../src/services/jobs/dbJobSync.js";
import { jobPathsFromRoot } from "../src/config/jobs.js";
import {
  markJobCanceledByNode,
  markWorkflowFailed,
  readWorkflowRecord,
} from "../src/services/jobs/jobProcess.js";
import { applyForcedCancel } from "../src/services/jobs/forcedCancel.js";
import { cancelJob } from "../src/services/jobs/jobQueue.js";

const repoRoot = path.resolve(process.cwd(), "..");
const hasDb = Boolean(process.env.DATABASE_URL?.trim());
const describeDb = hasDb ? test : test.skip;

describeDb("Phase 2 Lite jobs repository (Postgres)", async (t) => {
  await runMigrations();

  t.after(async () => {
    await closePool();
  });

  await t.test("claim queued job and cancel paths", async () => {
    const jobId = crypto.randomUUID();
    const userId = "phase2-test-user";
    const jobRoot = fs.mkdtempSync(path.join(os.tmpdir(), "mt-phase2-"));
    const videoPath = path.join(jobRoot, "input", "source.mp4");
    fs.mkdirSync(path.dirname(videoPath), { recursive: true });
    fs.writeFileSync(videoPath, "fake-video");
    writeMinimalWorkflow(jobRoot, jobId, userId, videoPath);

    t.after(async () => {
      await deleteJob(jobId);
      fs.rmSync(jobRoot, { recursive: true, force: true });
    });

    await insertJobQueued({
      jobId,
      userId,
      outputRoot: jobRoot,
      inputVideoPath: videoPath,
      originalSource: { type: "local_upload" },
    });

    let row = await getJobById(jobId);
    assert.equal(row?.status, "queued");

    const claimed = await claimJobByIdForTest("test-worker-1", jobId);
    assert.ok(claimed);
    assert.equal(claimed.status, "running");

    const canceling = await markJobCanceling(userId, jobId);
    assert.ok(canceling);
    assert.equal(canceling.status, "canceling");

    row = await getJobById(jobId);
    assert.equal(row?.status, "canceling");
  });

  await t.test("queued cancel and manual retry bump attempt_id", async () => {
    const jobId = crypto.randomUUID();
    const userId = "phase2-test-user-2";
    const jobRoot = fs.mkdtempSync(path.join(os.tmpdir(), "mt-phase2-"));
    const videoPath = path.join(jobRoot, "input", "source.mp4");
    fs.mkdirSync(path.dirname(videoPath), { recursive: true });
    fs.writeFileSync(videoPath, "fake-video");

    t.after(async () => {
      await deleteJob(jobId);
      fs.rmSync(jobRoot, { recursive: true, force: true });
    });

    await insertJobQueued({
      jobId,
      userId,
      outputRoot: jobRoot,
      inputVideoPath: videoPath,
    });

    const canceled = await markJobCanceledQueued(userId, jobId);
    assert.ok(canceled);
    assert.equal(canceled.status, "canceled");

    const retried = await retryJobInDb(userId, jobId);
    assert.ok(retried);
    assert.equal(retried.status, "queued");
    assert.equal(Number(retried.attempt_id), 2);
  });

  await t.test("running heartbeat does not write cancel.flag until DB canceling", async () => {
    const jobId = crypto.randomUUID();
    const userId = "phase2-cancel-flag";
    const jobRoot = fs.mkdtempSync(path.join(os.tmpdir(), "mt-phase2-"));
    const videoPath = path.join(jobRoot, "input", "source.mp4");
    fs.mkdirSync(path.dirname(videoPath), { recursive: true });
    fs.writeFileSync(videoPath, "fake");
    writeMinimalWorkflow(jobRoot, jobId, userId, videoPath);

    t.after(async () => {
      await deleteJob(jobId);
      fs.rmSync(jobRoot, { recursive: true, force: true });
    });

    await insertJobQueued({ jobId, userId, outputRoot: jobRoot, inputVideoPath: videoPath });
    const claimed = await claimJobByIdForTest("worker-cancel-test", jobId);
    assert.ok(claimed);

    const ctx = {
      attemptId: Number(claimed.attempt_id),
      claimedBy: String(claimed.claimed_by),
    };
    const paths = jobPathsFromRoot(jobRoot);

    await ensureCancelFlagForDbJob(jobId, jobRoot, ctx);
    assert.equal(fs.existsSync(paths.cancelFlagPath), false);

    await markJobCanceling(userId, jobId);
    await ensureCancelFlagForDbJob(jobId, jobRoot, ctx);
    assert.equal(fs.existsSync(paths.cancelFlagPath), true);

    const row = await getJobById(jobId);
    assert.ok(row?.cancel_acknowledged_at);
  });

  await t.test("DB running cancel writes cancel.flag immediately in API path", async () => {
    const jobId = crypto.randomUUID();
    const userId = "phase2-api-cancel-flag";
    const jobsRoot = fs.mkdtempSync(path.join(repoRoot, "artifacts", "test-jobs-"));
    const jobRoot = path.join(jobsRoot, jobId);
    const videoPath = path.join(jobRoot, "input", "source.mp4");
    fs.mkdirSync(path.dirname(videoPath), { recursive: true });
    fs.writeFileSync(videoPath, "fake");
    writeMinimalWorkflow(jobRoot, jobId, userId, videoPath, "running");

    t.after(async () => {
      await deleteJob(jobId);
      fs.rmSync(jobsRoot, { recursive: true, force: true });
    });

    await insertJobQueued({ jobId, userId, outputRoot: jobRoot, inputVideoPath: videoPath });
    await claimJobByIdForTest("worker-api-cancel", jobId);

    const prevJobsRoot = process.env.JOBS_ROOT;
    process.env.JOBS_ROOT = jobsRoot;
    try {
      const result = await cancelJob(jobId, userId);
      assert.equal(result.status, "canceling");
    } finally {
      if (prevJobsRoot === undefined) delete process.env.JOBS_ROOT;
      else process.env.JOBS_ROOT = prevJobsRoot;
    }

    const paths = jobPathsFromRoot(jobRoot);
    assert.equal(fs.existsSync(paths.cancelFlagPath), true);
    const wf = readWorkflowRecord(paths.workflowJsonPath);
    assert.equal(wf?.status, "running");
    assert.ok(wf?.cancel_requested_at);

    const row = await getJobById(jobId);
    assert.equal(row?.status, "canceling");
    assert.ok(row?.cancel_requested_at);
  });

  await t.test("stale worker ctx does not write cancel.flag", async () => {
    const jobId = crypto.randomUUID();
    const userId = "phase2-stale-cancel-ctx";
    const jobRoot = fs.mkdtempSync(path.join(os.tmpdir(), "mt-phase2-"));
    const videoPath = path.join(jobRoot, "input", "source.mp4");
    fs.mkdirSync(path.dirname(videoPath), { recursive: true });
    fs.writeFileSync(videoPath, "fake");
    writeMinimalWorkflow(jobRoot, jobId, userId, videoPath);

    t.after(async () => {
      await deleteJob(jobId);
      fs.rmSync(jobRoot, { recursive: true, force: true });
    });

    await insertJobQueued({ jobId, userId, outputRoot: jobRoot, inputVideoPath: videoPath });
    const claimed = await claimJobByIdForTest("worker-owner", jobId);
    assert.ok(claimed);
    await markJobCanceling(userId, jobId);

    const paths = jobPathsFromRoot(jobRoot);
    const staleCtx = {
      attemptId: Number(claimed.attempt_id) + 99,
      claimedBy: "other-worker",
    };
    await ensureCancelFlagForDbJob(jobId, jobRoot, staleCtx);
    assert.equal(fs.existsSync(paths.cancelFlagPath), false);

    await ensureCancelFlagForDbJob(jobId, jobRoot, {
      attemptId: Number(claimed.attempt_id),
      claimedBy: String(claimed.claimed_by),
    });
    assert.equal(fs.existsSync(paths.cancelFlagPath), true);
  });

  await t.test("failJobByWorker after claim when input missing", async () => {
    const jobId = crypto.randomUUID();
    const userId = "phase2-fail-prepare";
    const jobRoot = fs.mkdtempSync(path.join(os.tmpdir(), "mt-phase2-"));
    const missingPath = path.join(jobRoot, "input", "gone.mp4");

    t.after(async () => {
      await deleteJob(jobId);
      fs.rmSync(jobRoot, { recursive: true, force: true });
    });

    await insertJobQueued({
      jobId,
      userId,
      outputRoot: jobRoot,
      inputVideoPath: missingPath,
    });

    const claimed = await claimJobByIdForTest("worker-fail-test", jobId);
    assert.ok(claimed);

    const ok = await failJobByWorker({
      jobId,
      attemptId: Number(claimed.attempt_id),
      claimedBy: String(claimed.claimed_by),
      errorCode: "worker_prepare_failed",
      errorMessage: "Input video missing",
      retryable: true,
    });
    assert.equal(ok, true);

    const row = await getJobById(jobId);
    assert.equal(row?.status, "failed");
    assert.equal(row?.error?.error_code, "worker_prepare_failed");
    assert.equal(row?.error?.retryable, true);
  });

  await t.test("retry rejects failed when retryable is false", async () => {
    const jobId = crypto.randomUUID();
    const userId = "phase2-no-retry";
    const jobRoot = fs.mkdtempSync(path.join(os.tmpdir(), "mt-phase2-"));
    const videoPath = path.join(jobRoot, "input", "source.mp4");
    fs.mkdirSync(path.dirname(videoPath), { recursive: true });
    fs.writeFileSync(videoPath, "fake");

    t.after(async () => {
      await deleteJob(jobId);
      fs.rmSync(jobRoot, { recursive: true, force: true });
    });

    await insertJobQueued({ jobId, userId, outputRoot: jobRoot, inputVideoPath: videoPath });
    const pool = (await import("../src/db/pool.js")).getPool();
    await pool.query(
      `UPDATE jobs SET status = 'failed', retryable = false, error_code = 'fatal', completed_at = now()
       WHERE job_id = $1`,
      [jobId]
    );

    await assert.rejects(
      async () => retryJobInDb(userId, jobId),
      /cannot retry/
    );
  });

  await t.test("syncVideoStateToDb updates video_purged_at", async () => {
    const jobId = crypto.randomUUID();
    const userId = "phase2-purge-sync";
    const jobRoot = fs.mkdtempSync(path.join(os.tmpdir(), "mt-phase2-"));
    const videoPath = path.join(jobRoot, "input", "source.mp4");
    fs.mkdirSync(path.dirname(videoPath), { recursive: true });
    fs.writeFileSync(videoPath, "fake");

    t.after(async () => {
      await deleteJob(jobId);
      fs.rmSync(jobRoot, { recursive: true, force: true });
    });

    await insertJobQueued({ jobId, userId, outputRoot: jobRoot, inputVideoPath: videoPath });
    const purgedAt = "2026-06-01T12:00:00Z";
    await syncVideoStateToDb(jobId, {
      videoDownloadedAt: "2026-06-01T11:00:00Z",
      videoPurgedAt: purgedAt,
      videoStateVersion: 2,
    });

    const row = await getJobById(jobId);
    assert.equal(row?.video_purged_at, purgedAt);
    assert.equal(row?.video_state_version, 2);
  });

  await t.test("forced cancel updates DB with cancel_mode forced", async () => {
    const jobId = crypto.randomUUID();
    const userId = "phase2-forced-cancel";
    const jobRoot = fs.mkdtempSync(path.join(os.tmpdir(), "mt-phase2-"));
    const videoPath = path.join(jobRoot, "input", "source.mp4");
    fs.mkdirSync(path.dirname(videoPath), { recursive: true });
    fs.writeFileSync(videoPath, "fake-video");
    writeMinimalWorkflow(jobRoot, jobId, userId, videoPath, "running");

    t.after(async () => {
      await deleteJob(jobId);
      fs.rmSync(jobRoot, { recursive: true, force: true });
    });

    await insertJobQueued({
      jobId,
      userId,
      outputRoot: jobRoot,
      inputVideoPath: videoPath,
    });
    await claimJobByIdForTest("worker-forced-a", jobId);
    await markJobCanceling(userId, jobId);

    const pool = (await import("../src/db/pool.js")).getPool();
    await pool.query(
      `UPDATE jobs SET cancel_deadline_at = now() - interval '1 second' WHERE job_id = $1`,
      [jobId]
    );

    markJobCanceledByNode(jobRoot, { cancelMode: "forced" });
    const updated = await markJobForcedCanceledByWorker({
      jobId,
      attemptId: 1,
      claimedBy: "worker-forced-a",
    });
    assert.equal(updated, true);

    const row = await getJobById(jobId);
    assert.equal(row?.status, "canceled");
    assert.equal(row?.cancel_mode, "forced");
    assert.equal(row?.error, null);
    assert.ok(row?.completed_at);
  });

  await t.test("forced cancel does not apply for stale attempt_id", async () => {
    const jobId = crypto.randomUUID();
    const userId = "phase2-forced-stale";
    const jobRoot = fs.mkdtempSync(path.join(os.tmpdir(), "mt-phase2-"));
    const videoPath = path.join(jobRoot, "input", "source.mp4");
    fs.mkdirSync(path.dirname(videoPath), { recursive: true });
    fs.writeFileSync(videoPath, "fake");

    t.after(async () => {
      await deleteJob(jobId);
      fs.rmSync(jobRoot, { recursive: true, force: true });
    });

    await insertJobQueued({ jobId, userId, outputRoot: jobRoot, inputVideoPath: videoPath });
    await claimJobByIdForTest("worker-new", jobId);
    const pool = (await import("../src/db/pool.js")).getPool();
    await pool.query(
      `UPDATE jobs SET status = 'canceling', cancel_deadline_at = now() - interval '1 second',
       attempt_id = 2, claimed_by = 'worker-new' WHERE job_id = $1`,
      [jobId]
    );

    const updated = await markJobForcedCanceledByWorker({
      jobId,
      attemptId: 1,
      claimedBy: "worker-old",
    });
    assert.equal(updated, false);

    const row = await getJobById(jobId);
    assert.equal(row?.status, "canceling");
  });

  await t.test("applyForcedCancel with stale attempt does not touch workflow or kill", async () => {
    const jobId = crypto.randomUUID();
    const userId = "phase2-forced-stale-apply";
    const jobRoot = fs.mkdtempSync(path.join(os.tmpdir(), "mt-phase2-"));
    const videoPath = path.join(jobRoot, "input", "source.mp4");
    fs.mkdirSync(path.dirname(videoPath), { recursive: true });
    fs.writeFileSync(videoPath, "fake");
    writeMinimalWorkflow(jobRoot, jobId, userId, videoPath, "running");

    t.after(async () => {
      await deleteJob(jobId);
      fs.rmSync(jobRoot, { recursive: true, force: true });
    });

    await insertJobQueued({ jobId, userId, outputRoot: jobRoot, inputVideoPath: videoPath });
    await claimJobByIdForTest("worker-new", jobId);
    await markJobCanceling(userId, jobId);
    const pool = (await import("../src/db/pool.js")).getPool();
    await pool.query(
      `UPDATE jobs SET cancel_deadline_at = now() - interval '1 second',
       attempt_id = 2, claimed_by = 'worker-new' WHERE job_id = $1`,
      [jobId]
    );

    let killCalled = false;
    const ok = await applyForcedCancel({
      jobId,
      jobRoot,
      attemptId: 1,
      claimedBy: "worker-old",
      killFn: () => {
        killCalled = true;
      },
    });
    assert.equal(ok, false);
    assert.equal(killCalled, false);

    const wf = readWorkflowRecord(jobPathsFromRoot(jobRoot).workflowJsonPath);
    assert.equal(wf?.status, "running");
    assert.equal(wf?.cancel_mode, undefined);

    const row = await getJobById(jobId);
    assert.equal(row?.status, "canceling");
    assert.equal(Number(row?.attempt_id), 2);
  });

  await t.test("applyForcedCancel writes workflow cancel_mode forced", async () => {
    const jobId = crypto.randomUUID();
    const userId = "phase2-forced-wf";
    const jobRoot = fs.mkdtempSync(path.join(os.tmpdir(), "mt-phase2-"));
    const videoPath = path.join(jobRoot, "input", "source.mp4");
    fs.mkdirSync(path.dirname(videoPath), { recursive: true });
    fs.writeFileSync(videoPath, "fake");
    writeMinimalWorkflow(jobRoot, jobId, userId, videoPath, "running");

    t.after(async () => {
      await deleteJob(jobId);
      fs.rmSync(jobRoot, { recursive: true, force: true });
    });

    await insertJobQueued({ jobId, userId, outputRoot: jobRoot, inputVideoPath: videoPath });
    await claimJobByIdForTest("worker-fc", jobId);
    await markJobCanceling(userId, jobId);
    const pool = (await import("../src/db/pool.js")).getPool();
    await pool.query(
      `UPDATE jobs SET cancel_deadline_at = now() - interval '1 second' WHERE job_id = $1`,
      [jobId]
    );

    const ok = await applyForcedCancel({
      jobId,
      jobRoot,
      attemptId: 1,
      claimedBy: "worker-fc",
      killFn: () => {},
    });
    assert.equal(ok, true);

    const wf = readWorkflowRecord(jobPathsFromRoot(jobRoot).workflowJsonPath);
    assert.equal(wf?.status, "canceled");
    assert.equal(wf?.cancel_mode, "forced");
    assert.equal(wf?.error, null);
  });

  await t.test("applyForcedCancel when killFn throws keeps canceling and records error", async () => {
    const jobId = crypto.randomUUID();
    const userId = "phase2-forced-kill-fail";
    const jobRoot = fs.mkdtempSync(path.join(os.tmpdir(), "mt-phase2-"));
    const paths = jobPathsFromRoot(jobRoot);
    const videoPath = path.join(jobRoot, "input", "source.mp4");
    fs.mkdirSync(path.dirname(videoPath), { recursive: true });
    fs.writeFileSync(videoPath, "fake");
    writeMinimalWorkflow(jobRoot, jobId, userId, videoPath, "running");

    t.after(async () => {
      await deleteJob(jobId);
      fs.rmSync(jobRoot, { recursive: true, force: true });
    });

    await insertJobQueued({ jobId, userId, outputRoot: jobRoot, inputVideoPath: videoPath });
    await claimJobByIdForTest("worker-kill-fail", jobId);
    await markJobCanceling(userId, jobId);
    const pool = (await import("../src/db/pool.js")).getPool();
    await pool.query(
      `UPDATE jobs SET cancel_deadline_at = now() - interval '1 second' WHERE job_id = $1`,
      [jobId]
    );

    fs.mkdirSync(paths.logsDir, { recursive: true });
    fs.writeFileSync(
      paths.runnerPidPath,
      `${JSON.stringify({ pid: process.pid, spawnedAt: new Date().toISOString() })}\n`,
      "utf8"
    );

    const ok = await applyForcedCancel({
      jobId,
      jobRoot,
      attemptId: 1,
      claimedBy: "worker-kill-fail",
      killFn: () => {
        const err = new Error("simulated kill failure");
        // @ts-expect-error test-only
        err.code = "EPERM";
        throw err;
      },
    });
    assert.equal(ok, false);

    const row = await getJobById(jobId);
    assert.equal(row?.status, "canceling");
    assert.equal(row?.error?.error_code, "forced_cancel_kill_failed");
    assert.match(String(row?.error?.error_message || ""), /kill outcome: failed/);

    const wf = readWorkflowRecord(paths.workflowJsonPath);
    assert.equal(wf?.status, "running");
    assert.equal(wf?.cancel_mode, undefined);
  });

  await t.test("reconcile with stale attempt_id does not overwrite new attempt", async () => {
    const jobId = crypto.randomUUID();
    const userId = "phase2-attempt-guard";
    const jobRoot = fs.mkdtempSync(path.join(os.tmpdir(), "mt-phase2-"));
    const videoPath = path.join(jobRoot, "input", "source.mp4");
    fs.mkdirSync(path.dirname(videoPath), { recursive: true });
    fs.writeFileSync(videoPath, "fake");
    writeMinimalWorkflow(jobRoot, jobId, userId, videoPath, "failed");

    t.after(async () => {
      await deleteJob(jobId);
      fs.rmSync(jobRoot, { recursive: true, force: true });
    });

    await insertJobQueued({ jobId, userId, outputRoot: jobRoot, inputVideoPath: videoPath });
    const pool = (await import("../src/db/pool.js")).getPool();
    await pool.query(
      `UPDATE jobs SET status = 'failed', retryable = true, attempt_id = 2, claimed_by = 'worker-b', completed_at = now()
       WHERE job_id = $1`,
      [jobId]
    );

    markWorkflowFailed(jobRoot, {
      errorCode: "stale_write",
      errorMessage: "should not apply",
      retryable: false,
    });
    const paths = jobPathsFromRoot(jobRoot);
    const wf = readWorkflowRecord(paths.workflowJsonPath);
    wf.status = "succeeded";
    fs.writeFileSync(paths.workflowJsonPath, `${JSON.stringify(wf, null, 2)}\n`);

    const applied = await reconcileJobFromWorkflow(jobRoot, {
      attemptId: 1,
      claimedBy: "worker-a",
    });
    assert.equal(applied, false);

    const row = await getJobById(jobId);
    assert.equal(row?.status, "failed");
    assert.equal(Number(row?.attempt_id), 2);
  });
});

/**
 * @param {string} jobRoot
 * @param {string} jobId
 * @param {string} userId
 * @param {string} videoPath
 * @param {string} [status]
 */
function writeMinimalWorkflow(jobRoot, jobId, userId, videoPath, status = "queued") {
  const paths = jobPathsFromRoot(jobRoot);
  fs.mkdirSync(path.dirname(paths.workflowJsonPath), { recursive: true });
  fs.writeFileSync(
    paths.workflowJsonPath,
    `${JSON.stringify(
      {
        job_id: jobId,
        user_id: userId,
        status,
        input_video_path: videoPath,
        output_root: jobRoot,
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      },
      null,
      2
    )}\n`
  );
}

async function deleteJob(jobId) {
  const pool = (await import("../src/db/pool.js")).getPool();
  await pool.query("DELETE FROM jobs WHERE job_id = $1", [jobId]);
}

/**
 * @param {string} workerId
 * @param {string} jobId
 */
async function claimJobByIdForTest(workerId, jobId) {
  const pool = (await import("../src/db/pool.js")).getPool();
  const result = await pool.query(
    `UPDATE jobs SET
       status = 'running',
       claimed_at = now(),
       claimed_by = $1,
       last_heartbeat_at = now(),
       started_at = COALESCE(started_at, now()),
       updated_at = now()
     WHERE job_id = $2 AND status = 'queued' AND cancel_requested_at IS NULL
     RETURNING *`,
    [workerId, jobId]
  );
  if (result.rowCount === 0) return null;
  const { rowToRecord } = await import("../src/db/jobsRepository.js");
  return rowToRecord(result.rows[0]);
}
