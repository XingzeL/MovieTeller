import express from "express";

import {
  readWorkflowProgressFromLog,
  resolveWorkflowLogPath,
} from "../services/workflow/readWorkflowProgress.js";

const router = express.Router();

/**
 * GET /api/workflow/progress?outputRoot=test_artifacts
 * Overall job percent for frontend (reads logs/workflow.jsonl).
 */
router.get("/workflow/progress", async (req, res) => {
  const outputRoot = String(req.query.outputRoot || "").trim();
  if (!outputRoot) {
    return res.status(400).json({ error: "outputRoot query parameter is required" });
  }

  const resolved = resolveWorkflowLogPath(outputRoot);
  if (resolved.error) {
    return res.status(400).json({ error: resolved.error });
  }

  try {
    const progress = await readWorkflowProgressFromLog(resolved.logPath);
    return res.json({
      outputRoot,
      logPath: resolved.logPath,
      progress,
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return res.status(500).json({ error: message });
  }
});

export default router;
