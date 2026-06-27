import express from "express";

import { respondDatabaseError } from "../db/errors.js";
import { respondBillingError } from "../services/billing/errors.js";
import { parseRemoteVideo } from "../services/media/parseRemoteVideo.js";
import {
  extractSourceUrlFromBody,
  validateSourceUrlAsync,
} from "../services/media/validateSourceUrl.js";

const router = express.Router();

router.post("/videos/parse", async (req, res) => {
  const sourceUrl = extractSourceUrlFromBody(req.body);
  if (!sourceUrl) {
    return res.status(400).json({ error: "sourceUrl is required" });
  }

  try {
    const urlValidation = await validateSourceUrlAsync(sourceUrl);
    if (!urlValidation.ok) {
      return res.status(400).json({ error: urlValidation.message });
    }

    const parsed = await parseRemoteVideo(urlValidation.url);
    return res.json({
      sourceUrl: urlValidation.url,
      ...parsed,
    });
  } catch (err) {
    if (respondBillingError(res, err)) return;
    return respondDatabaseError(res, err);
  }
});

export default router;
