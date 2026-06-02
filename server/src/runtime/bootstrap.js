import { getRunMode } from "./runMode.js";
import { startCombinedRuntime } from "./combined.js";
import { startApiServer } from "./apiServer.js";
import { startWorkerRuntime } from "./workerRuntime.js";
import { ensureDatabaseReady, assertDatabaseConfigured } from "../db/ensure.js";
import { isDbEnabled } from "../db/database.js";

/** @deprecated Use startCombinedRuntime */
export { startCombinedRuntime as startApiRuntime } from "./combined.js";

/**
 * Start runtime based on MOVIE_TELLER_RUN_MODE / RUN_MODE.
 * @param {{ port?: number, runScheduler?: boolean, pollMs?: number }} [opts]
 */
export async function startBootstrapRuntime(opts = {}) {
  assertDatabaseConfigured();
  if (isDbEnabled()) {
    await ensureDatabaseReady();
  }
  const mode = getRunMode();
  if (mode === "api") {
    return startApiServer(opts);
  }
  if (mode === "worker") {
    return startWorkerRuntime(opts);
  }
  return startCombinedRuntime(opts);
}

export { startCombinedRuntime, startApiServer, startWorkerRuntime };
