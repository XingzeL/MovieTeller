import { loadConfig } from "../config/index.js";
import { getJobsRoot } from "../config/jobs.js";
import { createApp } from "../app.js";
import { recoverJobsOnStartup } from "../services/jobs/jobRecovery.js";
import { startRetentionScheduler } from "../services/retention/retentionScheduler.js";

/**
 * @param {{ port?: number, runScheduler?: boolean }} [opts]
 */
export function startApiRuntime(opts = {}) {
  loadConfig();
  getJobsRoot();

  const recovery = recoverJobsOnStartup();
  if (recovery.recovered > 0) {
    console.warn(`Recovered ${recovery.recovered} stale job(s) on startup`);
  }

  let scheduler = { stop: () => {} };
  if (opts.runScheduler !== false && process.env.RUN_SCHEDULER !== "0") {
    scheduler = startRetentionScheduler();
  }

  const app = createApp();
  const port = opts.port ?? (Number(process.env.PORT) || 3001);

  const server = app.listen(port, () => {
    console.log(`Server listening on http://localhost:${port}`);
  });

  return { app, server, scheduler };
}
