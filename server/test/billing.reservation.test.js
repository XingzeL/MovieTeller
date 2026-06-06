import assert from "node:assert/strict";
import crypto from "node:crypto";
import test from "node:test";

import { closePool, getPool } from "../src/db/pool.js";
import { runMigrations } from "../src/db/ensure.js";
import { getUserBalance } from "../src/db/balancesRepository.js";
import { resolveProcessingRange } from "../src/services/billing/resolveProcessingRange.js";
import { reserveQuotaAndInsertJob } from "../src/services/billing/reserveQuota.js";
import { releaseQuota } from "../src/services/billing/releaseQuota.js";
import { deleteJobById } from "../src/db/jobsRepository.js";
import { upsertUserOnLogin } from "../src/services/billing/upsertUserOnLogin.js";
import { PlanQuotaExhaustedError } from "../src/services/billing/errors.js";

const hasDb = Boolean(process.env.DATABASE_URL?.trim());
const describeDb = hasDb ? test : test.skip;

describeDb("billing reservation", async (t) => {
  await runMigrations();

  t.after(async () => {
    await closePool();
  });

  await t.test("resolveProcessingRange clips to monthly quota", () => {
    const range = resolveProcessingRange({
      sourceDurationSec: 600,
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
      (err) => err instanceof PlanQuotaExhaustedError
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
