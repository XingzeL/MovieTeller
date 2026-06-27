import { loadConfig } from "../config/index.js";
import { getJobsRoot } from "../config/jobs.js";
import { runStartupRecovery } from "./startupRecovery.js";
import { cleanupStaleDownloadDirs } from "../services/media/validateSourceUrl.js";
import { startWorkerLoop, stopWorkerLoop } from "./queueWorker.js";
import { isWorkerRunMode } from "./runMode.js";

/**
 * Worker-only process: recovery for orphan running + queue poll/spawn.
 * @param {{ pollMs?: number }} [opts]
 */
export function startWorkerRuntime(opts = {}) {
  loadConfig();
  getJobsRoot();

  if (!isWorkerRunMode()) {
    console.warn(
      "[runtime] startWorkerRuntime called but MOVIE_TELLER_RUN_MODE is not worker"
    );
  }

  const recovery = runStartupRecovery();
  if (recovery.recovered > 0) {
    console.warn(`Worker recovered ${recovery.recovered} orphan running job(s)`);
  }

  const cleaned = cleanupStaleDownloadDirs();
  if (cleaned.removed > 0) {
    console.warn(`Worker cleaned ${cleaned.removed} stale download temp dir(s)`);
  }

  const worker = startWorkerLoop({ pollMs: opts.pollMs });
  console.log("[runtime] worker loop started");

  return {
    stop() {
      stopWorkerLoop(worker);
    },
  };
}
