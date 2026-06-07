import express from "express";

import { respondDatabaseError } from "../db/errors.js";
import { isDbEnabled } from "../db/database.js";
import { isProductionEnv } from "../middleware/userId.js";
import {
  MockPurchaseError,
  mockPurchase,
} from "../services/billing/mockPurchase.js";

const router = express.Router();

router.post("/billing/mock-purchase", async (req, res) => {
  if (isProductionEnv()) {
    return res.status(404).json({ error: "not found" });
  }
  if (!isDbEnabled()) {
    return res.status(503).json({ error: "database unavailable" });
  }

  const kind = req.body?.kind;
  const id = req.body?.id;
  try {
    const result = await mockPurchase(req.user.id, { kind, id });
    return res.json(result);
  } catch (err) {
    if (err instanceof MockPurchaseError) {
      return res.status(err.statusCode).json({
        error: err.message,
        code: err.code,
      });
    }
    return respondDatabaseError(res, err);
  }
});

export default router;
