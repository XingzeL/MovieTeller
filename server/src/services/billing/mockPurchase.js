import {
  addPurchasedQuota,
  getNarrationAvailableMinutes,
  getProcessingAvailableMinutes,
  getUserBalance,
  lockUserBalance,
} from "../../db/balancesRepository.js";
import { getPlanByCode } from "../../db/plansRepository.js";
import { insertQuotaPurchase } from "../../db/quotaPurchasesRepository.js";
import { getPool } from "../../db/pool.js";
import { switchActiveSubscription } from "../../db/usersRepository.js";
import { ensureActiveBillingPeriod } from "./ensureActiveBillingPeriod.js";
import { upsertUserOnLogin } from "./upsertUserOnLogin.js";

/** @type {Record<string, { processingMinutes: number, narrationMinutes: number, maxVideoDurationSec: number }>} */
export const MOCK_ADDON_CATALOG = {
  "processing-120": {
    processingMinutes: 120,
    narrationMinutes: 0,
    maxVideoDurationSec: 900,
  },
  s: { processingMinutes: 60, narrationMinutes: 60, maxVideoDurationSec: 900 },
  m: { processingMinutes: 150, narrationMinutes: 150, maxVideoDurationSec: 1800 },
  l: { processingMinutes: 300, narrationMinutes: 300, maxVideoDurationSec: 3000 },
};

export class MockPurchaseError extends Error {
  constructor(message, code = "invalid_purchase") {
    super(message);
    this.name = "MockPurchaseError";
    this.code = code;
    this.statusCode = 400;
  }
}

/**
 * @param {string} userId
 * @param {{ kind: string, id: string }} input
 */
export async function mockPurchase(userId, input) {
  const kind = String(input.kind || "").trim();
  const id = String(input.id || "").trim();
  if (!kind || !id) {
    throw new MockPurchaseError("kind and id are required");
  }

  const client = await getPool().connect();
  try {
    await client.query("BEGIN");
    await upsertUserOnLogin(userId, client);
    await ensureActiveBillingPeriod(userId, client);

    const balance = await lockUserBalance(userId, client);
    if (!balance) {
      throw new MockPurchaseError("user balance missing", "balance_missing");
    }

    let addedProcessingMinutes = 0;
    let addedNarrationMinutes = 0;
    let maxVideoDurationSec = null;
    let planCode = null;

    if (kind === "plan") {
      if (id === "free") {
        throw new MockPurchaseError("free plan does not require purchase");
      }
      const plan = await getPlanByCode(id, client);
      if (!plan) {
        throw new MockPurchaseError("unknown plan");
      }
      addedProcessingMinutes = Number(plan.quota_minutes_per_month) || 0;
      addedNarrationMinutes =
        Number(plan.narration_quota_minutes_per_month) || addedProcessingMinutes;
      maxVideoDurationSec = Number(plan.max_video_duration_sec) || null;
      await switchActiveSubscription(userId, plan.id, client);
      planCode = plan.code;
    } else if (kind === "addon") {
      const addon = MOCK_ADDON_CATALOG[id];
      if (!addon) {
        throw new MockPurchaseError("unknown addon");
      }
      addedProcessingMinutes = addon.processingMinutes;
      addedNarrationMinutes = addon.narrationMinutes;
      maxVideoDurationSec = addon.maxVideoDurationSec;
    } else {
      throw new MockPurchaseError("invalid kind");
    }

    await addPurchasedQuota(
      userId,
      {
        processingMinutes: addedProcessingMinutes,
        narrationMinutes: addedNarrationMinutes,
        maxVideoDurationSec,
      },
      client
    );

    await insertQuotaPurchase(
      {
        userId,
        kind,
        productId: id,
        processingMinutes: addedProcessingMinutes,
        narrationMinutes: addedNarrationMinutes,
        maxVideoDurationSec,
      },
      client
    );

    await client.query("COMMIT");

    const updated = await getUserBalance(userId);
    return {
      ok: true,
      kind,
      id,
      planCode,
      addedProcessingMinutes,
      addedNarrationMinutes,
      maxVideoDurationSec,
      processingRemainingMinutes: updated
        ? getProcessingAvailableMinutes(updated)
        : 0,
      narrationRemainingMinutes: updated
        ? getNarrationAvailableMinutes(updated)
        : 0,
    };
  } catch (err) {
    await client.query("ROLLBACK");
    throw err;
  } finally {
    client.release();
  }
}
