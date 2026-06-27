import { loadConfig } from "../config/index.js";
import { getJobsRoot } from "../config/jobs.js";
import { createApp } from "../app.js";
import { runStartupRecovery } from "./startupRecovery.js";
import { startRetentionScheduler } from "../services/retention/retentionScheduler.js";
import { cleanupStaleDownloadDirs } from "../services/media/validateSourceUrl.js";
import { startRemoteDownloadLoop } from "../services/jobs/remoteDownloadWorker.js";
import { isCombinedRunMode } from "./runMode.js";

/**
 * Default Phase 1 runtime: recovery + retention + HTTP + in-process jobQueue spawn.
 * @param {{ port?: number, runScheduler?: boolean }} [opts]
 */
export function startCombinedRuntime(opts = {}) {
  loadConfig();
  getJobsRoot();

  if (!isCombinedRunMode()) {
    console.warn(
      "[runtime] startCombinedRuntime called but MOVIE_TELLER_RUN_MODE is not combined"
    );
  }

  const recovery = runStartupRecovery();
  if (recovery.recovered > 0) {
    console.warn(`Recovered ${recovery.recovered} stale job(s) on startup`);
  }

  const cleaned = cleanupStaleDownloadDirs();
  if (cleaned.removed > 0) {
    console.warn(`Cleaned ${cleaned.removed} stale download temp dir(s)`);
  }

  startRemoteDownloadLoop();

  let scheduler = { stop: () => {} };
  if (opts.runScheduler !== false && process.env.RUN_SCHEDULER !== "0") {
    scheduler = startRetentionScheduler();
  }

  const app = createApp();
  const port = opts.port ?? (Number(process.env.PORT) || 3001);
  const server = app.listen(port, () => {
    console.log(
      `Server listening on http://localhost:${port} (run_mode=combined)`
    );
  });

  return { app, server, scheduler };
}
