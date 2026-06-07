import assert from "node:assert/strict";
import crypto from "node:crypto";
import test from "node:test";

import { closePool, getPool } from "../src/db/pool.js";
import { runMigrations } from "../src/db/ensure.js";
import { getUserBalance } from "../src/db/balancesRepository.js";
import {
  buildClipReasons,
  resolveProcessingRange,
} from "../src/services/billing/resolveProcessingRange.js";
import { reserveQuotaAndInsertJob } from "../src/services/billing/reserveQuota.js";
import { releaseQuota } from "../src/services/billing/releaseQuota.js";
import { deleteJobById } from "../src/db/jobsRepository.js";
import { upsertUserOnLogin } from "../src/services/billing/upsertUserOnLogin.js";
import { PlanQuotaExhaustedError } from "../src/services/billing/errors.js";
import { toCreateJobApiResponse } from "../src/services/jobs/jobQueue.js";

const hasDb = Boolean(process.env.DATABASE_URL?.trim());
const describeDb = hasDb ? test : test.skip;

test("toCreateJobApiResponse includes quota clip fields", () => {
  const response = toCreateJobApiResponse({
    jobId: "job-clip",
    status: "queued",
    createdAt: "2026-01-01T00:00:00Z",
    outputRoot: "/tmp/job-clip",
    sourceDurationSec: 600,
    processedDurationSec: 180,
    quotaClipApplied: true,
    quotaClipReasons: [
      {
        code: "plan_max_video",
        category: "plan_limit",
        limitSeconds: 180,
        limitMinutes: 3,
      },
    ],
    primaryClipReason: "plan_max_video",
  });
  assert.equal(response.quotaClipApplied, true);
  assert.equal(response.sourceDurationSec, 600);
  assert.equal(response.processedDurationSec, 180);
  assert.equal(response.quotaClipReasons.length, 1);
});

test("resolveProcessingRange clips to monthly quota", () => {
  const range = resolveProcessingRange({
    sourceDurationSec: 600,
    enableSpeech: false,
    plan: {
      code: "free",
      max_video_duration_sec: 180,
      max_daily_minutes: null,
    },
    balance: { remaining_minutes: 5, reserved_minutes: 0 },
    dailyUsage: { consumed_minutes: 0, reserved_minutes: 0 },
  });
  assert.equal(range.endPoint, 180);
  assert.equal(range.quotaClipApplied, true);
  assert.equal(range.needMinutes, 3);
  assert.equal(range.quotaPolicy.primaryClipReason, "plan_max_video");
  assert.ok(
    range.quotaPolicy.clipReasons.some((item) => item.code === "plan_max_video")
  );
});

test("clip reasons identify processing quota limit", () => {
  const { clipReasons, primaryClipReason } = buildClipReasons({
    sourceDurationSec: 600,
    planMaxSec: 1800,
    processingAvailableSec: 120,
    narrationAvailableSec: Number.POSITIVE_INFINITY,
    dailyAvailableSec: Number.POSITIVE_INFINITY,
    enableSpeech: false,
  });
  assert.equal(primaryClipReason, "processing_quota");
  assert.deepEqual(
    clipReasons.map((item) => item.code),
    ["processing_quota"]
  );
});

test("clip reasons identify narration quota limit", () => {
  const { primaryClipReason, clipReasons } = buildClipReasons({
    sourceDurationSec: 600,
    planMaxSec: 1800,
    processingAvailableSec: 1800,
    narrationAvailableSec: 60,
    dailyAvailableSec: Number.POSITIVE_INFINITY,
    enableSpeech: true,
  });
  assert.equal(primaryClipReason, "narration_quota");
  assert.ok(clipReasons.some((item) => item.code === "narration_quota"));
});

describeDb("billing reservation", async (t) => {
  await runMigrations();

  t.after(async () => {
    await closePool();
  });

  await t.test("new user gets free plan balance", async () => {
    const userId = `billing-free-${crypto.randomUUID()}`;
    t.after(async () => {
      await cleanupUser(userId);
    });
    await upsertUserOnLogin(userId);
    const balance = await getUserBalance(userId);
    assert.ok(balance);
    assert.equal(balance.remaining_minutes, 5);
    assert.equal(balance.narration_remaining_minutes, 5);
  });

  await t.test("second reservation clips to remaining quota and third fails", async () => {
    const userId = `billing-exhaust-${crypto.randomUUID()}`;
    const jobId1 = crypto.randomUUID();
    const jobId2 = crypto.randomUUID();
    const jobId3 = crypto.randomUUID();
    t.after(async () => {
      await deleteJobById(jobId1);
      await deleteJobById(jobId2);
      await deleteJobById(jobId3);
      await cleanupUser(userId);
    });

    await reserveQuotaAndInsertJob({
      jobId: jobId1,
      userId,
      outputRoot: `/tmp/${jobId1}`,
      inputVideoPath: `/tmp/${jobId1}/input/source.mp4`,
      sourceDurationSec: 180,
    });

    const second = await reserveQuotaAndInsertJob({
      jobId: jobId2,
      userId,
      outputRoot: `/tmp/${jobId2}`,
      inputVideoPath: `/tmp/${jobId2}/input/source.mp4`,
      sourceDurationSec: 180,
    });
    assert.equal(second.needMinutes, 2);
    assert.equal(second.processedDurationSec, 120);

    await assert.rejects(
      () =>
        reserveQuotaAndInsertJob({
          jobId: jobId3,
          userId,
          outputRoot: `/tmp/${jobId3}`,
          inputVideoPath: `/tmp/${jobId3}/input/source.mp4`,
          sourceDurationSec: 180,
        }),
      (err) =>
        err instanceof PlanQuotaExhaustedError &&
        err.reason === "processing_quota_exhausted"
    );
  });

  await t.test("releaseQuota restores reserved minutes", async () => {
    const userId = `billing-release-${crypto.randomUUID()}`;
    const jobId = crypto.randomUUID();
    t.after(async () => {
      await deleteJobById(jobId);
      await cleanupUser(userId);
    });

    const range = await reserveQuotaAndInsertJob({
      jobId,
      userId,
      outputRoot: `/tmp/${jobId}`,
      inputVideoPath: `/tmp/${jobId}/input/source.mp4`,
      sourceDurationSec: 120,
    });

    let balance = await getUserBalance(userId);
    assert.equal(balance.reserved_minutes, range.needMinutes);

    await releaseQuota(userId, range.needMinutes);
    balance = await getUserBalance(userId);
    assert.equal(balance.reserved_minutes, 0);
    assert.equal(balance.remaining_minutes, 5);
  });

  await t.test("narration quota limits speech jobs only", async () => {
    const userId = `billing-narration-${crypto.randomUUID()}`;
    const noSpeechJobId = crypto.randomUUID();
    const speechJobId = crypto.randomUUID();
    t.after(async () => {
      await deleteJobById(noSpeechJobId);
      await deleteJobById(speechJobId);
      await cleanupUser(userId);
    });

    await upsertUserOnLogin(userId);
    await getPool().query(
      `UPDATE user_balances SET
         narration_remaining_minutes = 1,
         narration_reserved_minutes = 0
       WHERE user_id = $1`,
      [userId]
    );

    const noSpeech = await reserveQuotaAndInsertJob({
      jobId: noSpeechJobId,
      userId,
      outputRoot: `/tmp/${noSpeechJobId}`,
      inputVideoPath: `/tmp/${noSpeechJobId}/input/source.mp4`,
      sourceDurationSec: 180,
      enableSpeech: false,
    });
    assert.equal(noSpeech.needMinutes, 3);
    assert.equal(noSpeech.needNarrationMinutes, 0);

    const speech = await reserveQuotaAndInsertJob({
      jobId: speechJobId,
      userId,
      outputRoot: `/tmp/${speechJobId}`,
      inputVideoPath: `/tmp/${speechJobId}/input/source.mp4`,
      sourceDurationSec: 180,
      enableSpeech: true,
    });
    assert.equal(speech.needMinutes, 1);
    assert.equal(speech.needNarrationMinutes, 1);
    assert.equal(speech.processedDurationSec, 60);
  });

  await t.test("missing enableSpeech defaults to narration enabled", async () => {
    const userId = `billing-default-speech-${crypto.randomUUID()}`;
    const jobId = crypto.randomUUID();
    t.after(async () => {
      await deleteJobById(jobId);
      await cleanupUser(userId);
    });

    await upsertUserOnLogin(userId);
    await getPool().query(
      `UPDATE user_balances SET
         narration_remaining_minutes = 1,
         narration_reserved_minutes = 0
       WHERE user_id = $1`,
      [userId]
    );

    const range = await reserveQuotaAndInsertJob({
      jobId,
      userId,
      outputRoot: `/tmp/${jobId}`,
      inputVideoPath: `/tmp/${jobId}/input/source.mp4`,
      sourceDurationSec: 180,
    });

    assert.equal(range.enableSpeech, true);
    assert.equal(range.needMinutes, 1);
    assert.equal(range.needNarrationMinutes, 1);
  });

  await t.test("processing quota exhausted reports processing reason", async () => {
    const userId = `billing-processing-empty-${crypto.randomUUID()}`;
    const jobId = crypto.randomUUID();
    t.after(async () => {
      await deleteJobById(jobId);
      await cleanupUser(userId);
    });

    await upsertUserOnLogin(userId);
    await getPool().query(
      `UPDATE user_balances SET
         remaining_minutes = 0,
         reserved_minutes = 0,
         narration_remaining_minutes = 5,
         narration_reserved_minutes = 0
       WHERE user_id = $1`,
      [userId]
    );

    await assert.rejects(
      () =>
        reserveQuotaAndInsertJob({
          jobId,
          userId,
          outputRoot: `/tmp/${jobId}`,
          inputVideoPath: `/tmp/${jobId}/input/source.mp4`,
          sourceDurationSec: 60,
          enableSpeech: false,
        }),
      (err) =>
        err instanceof PlanQuotaExhaustedError &&
        err.reason === "processing_quota_exhausted"
    );
  });

  await t.test("narration quota exhausted reports narration reason", async () => {
    const userId = `billing-narration-empty-${crypto.randomUUID()}`;
    const jobId = crypto.randomUUID();
    t.after(async () => {
      await deleteJobById(jobId);
      await cleanupUser(userId);
    });

    await upsertUserOnLogin(userId);
    await getPool().query(
      `UPDATE user_balances SET
         remaining_minutes = 5,
         reserved_minutes = 0,
         narration_remaining_minutes = 0,
         narration_reserved_minutes = 0
       WHERE user_id = $1`,
      [userId]
    );

    await assert.rejects(
      () =>
        reserveQuotaAndInsertJob({
          jobId,
          userId,
          outputRoot: `/tmp/${jobId}`,
          inputVideoPath: `/tmp/${jobId}/input/source.mp4`,
          sourceDurationSec: 60,
          enableSpeech: true,
        }),
      (err) =>
        err instanceof PlanQuotaExhaustedError &&
        err.reason === "narration_quota_exhausted"
    );
  });
});

/**
 * @param {string} userId
 */
async function cleanupUser(userId) {
  const pool = getPool();
  await pool.query("DELETE FROM usage_ledger WHERE user_id = $1", [userId]);
  await pool.query("DELETE FROM jobs WHERE user_id = $1", [userId]);
  await pool.query("DELETE FROM user_daily_usage WHERE user_id = $1", [userId]);
  await pool.query("DELETE FROM user_balances WHERE user_id = $1", [userId]);
  await pool.query("DELETE FROM user_subscriptions WHERE user_id = $1", [userId]);
  await pool.query("DELETE FROM users WHERE id = $1", [userId]);
}
