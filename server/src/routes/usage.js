import express from "express";

import { respondDatabaseError } from "../db/errors.js";
import { isDbEnabled } from "../db/database.js";
import { getUsageForUser } from "../services/billing/getUsageSummary.js";

const router = express.Router();

router.get("/usage", async (req, res) => {
  if (!isDbEnabled()) {
    return res.status(503).json({ error: "database unavailable" });
  }
  try {
    const limitRaw = req.query.limit;
    const offsetRaw = req.query.offset;
    const limit =
      limitRaw !== undefined && String(limitRaw).trim() !== ""
        ? Number(limitRaw)
        : undefined;
    const offset =
      offsetRaw !== undefined && String(offsetRaw).trim() !== ""
        ? Number(offsetRaw)
        : undefined;
    const payload = await getUsageForUser(req.user.id, {
      limit: Number.isNaN(limit) ? undefined : limit,
      offset: Number.isNaN(offset) ? undefined : offset,
    });
    return res.json(payload);
  } catch (err) {
    return respondDatabaseError(res, err);
  }
});

export default router;
