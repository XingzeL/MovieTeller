import { loadConfig } from "../config/index.js";
import { getJobsRoot } from "../config/jobs.js";
import { createApp } from "../app.js";
import { runStartupRecovery } from "./startupRecovery.js";
import { startRetentionScheduler } from "../services/retention/retentionScheduler.js";
import { isApiRunMode } from "./runMode.js";

/**
 * API-only HTTP server (no combined recovery; no spawn in jobQueue).
 * @param {{ port?: number, runScheduler?: boolean }} [opts]
 */
export function startApiServer(opts = {}) {
  loadConfig();
  getJobsRoot();

  if (!isApiRunMode()) {
    console.warn(
      "[runtime] startApiServer called but MOVIE_TELLER_RUN_MODE is not api"
    );
  }

  const recovery = runStartupRecovery();
  if (recovery.recovered > 0) {
    console.warn(`Recovered ${recovery.recovered} stale job(s) on API startup`);
  }

  let scheduler = { stop: () => {} };
  if (opts.runScheduler !== false && process.env.RUN_SCHEDULER !== "0") {
    scheduler = startRetentionScheduler();
  }

  const app = createApp();
  const port = opts.port ?? (Number(process.env.PORT) || 3001);
  const server = app.listen(port, () => {
    console.log(`API server listening on http://localhost:${port} (run_mode=api)`);
  });

  return { app, server, scheduler };
}
