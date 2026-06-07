import assert from "node:assert/strict";
import crypto from "node:crypto";
import test from "node:test";

import { closePool, getPool } from "../src/db/pool.js";
import { runMigrations } from "../src/db/ensure.js";
import { getUserBalance } from "../src/db/balancesRepository.js";
import { getActiveSubscription } from "../src/db/usersRepository.js";
import {
  MockPurchaseError,
  mockPurchase,
} from "../src/services/billing/mockPurchase.js";
import { upsertUserOnLogin } from "../src/services/billing/upsertUserOnLogin.js";

const hasDb = Boolean(process.env.DATABASE_URL?.trim());
const describeDb = hasDb ? test : test.skip;

describeDb("billing mock purchase", async (t) => {
  await runMigrations();

  t.after(async () => {
    await closePool();
  });

  await t.test("addon adds processing and narration minutes", async () => {
    const userId = `mock-addon-${crypto.randomUUID()}`;
    t.after(async () => cleanupUser(userId));

    await upsertUserOnLogin(userId);
    const before = await getUserBalance(userId);

    const result = await mockPurchase(userId, { kind: "addon", id: "s" });
    assert.equal(result.addedProcessingMinutes, 60);
    assert.equal(result.addedNarrationMinutes, 60);

    const after = await getUserBalance(userId);
    assert.equal(
      Number(after.remaining_minutes),
      Number(before.remaining_minutes) + 60
    );
    assert.equal(
      Number(after.narration_remaining_minutes),
      Number(before.narration_remaining_minutes) + 60
    );
    assert.equal(Number(after.bonus_processing_minutes), 60);
    assert.equal(Number(after.max_video_duration_sec_override), 900);

    const purchases = await getPool().query(
      "SELECT * FROM quota_purchases WHERE user_id = $1",
      [userId]
    );
    assert.equal(purchases.rowCount, 1);
  });

  await t.test("processing addon adds processing only", async () => {
    const userId = `mock-processing-${crypto.randomUUID()}`;
    t.after(async () => cleanupUser(userId));

    await upsertUserOnLogin(userId);
    const before = await getUserBalance(userId);

    await mockPurchase(userId, { kind: "addon", id: "processing-120" });

    const after = await getUserBalance(userId);
    assert.equal(
      Number(after.remaining_minutes),
      Number(before.remaining_minutes) + 120
    );
    assert.equal(
      Number(after.narration_remaining_minutes),
      Number(before.narration_remaining_minutes)
    );
  });

  await t.test("plan purchase switches subscription and adds quota", async () => {
    const userId = `mock-plan-${crypto.randomUUID()}`;
    t.after(async () => cleanupUser(userId));

    await upsertUserOnLogin(userId);
    const before = await getUserBalance(userId);

    const result = await mockPurchase(userId, { kind: "plan", id: "pro" });
    assert.equal(result.planCode, "pro");
    assert.equal(result.addedProcessingMinutes, 300);
    assert.equal(result.addedNarrationMinutes, 300);

    const subscription = await getActiveSubscription(userId);
    assert.equal(subscription.plan_code, "pro");

    const after = await getUserBalance(userId);
    assert.equal(
      Number(after.remaining_minutes),
      Number(before.remaining_minutes) + 300
    );
    assert.equal(
      Number(after.narration_remaining_minutes),
      Number(before.narration_remaining_minutes) + 300
    );
  });

  await t.test("free plan purchase is rejected", async () => {
    const userId = `mock-free-${crypto.randomUUID()}`;
    t.after(async () => cleanupUser(userId));

    await upsertUserOnLogin(userId);
    await assert.rejects(
      () => mockPurchase(userId, { kind: "plan", id: "free" }),
      (err) => err instanceof MockPurchaseError
    );
  });
});

/**
 * @param {string} userId
 */
async function cleanupUser(userId) {
  const pool = getPool();
  await pool.query("DELETE FROM quota_purchases WHERE user_id = $1", [userId]);
  await pool.query("DELETE FROM usage_ledger WHERE user_id = $1", [userId]);
  await pool.query("DELETE FROM jobs WHERE user_id = $1", [userId]);
  await pool.query("DELETE FROM user_daily_usage WHERE user_id = $1", [userId]);
  await pool.query("DELETE FROM user_balances WHERE user_id = $1", [userId]);
  await pool.query("DELETE FROM user_subscriptions WHERE user_id = $1", [userId]);
  await pool.query("DELETE FROM users WHERE id = $1", [userId]);
}
