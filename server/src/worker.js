import { assertDatabaseConfigured, ensureDatabaseReady } from "./db/ensure.js";
import { isDbEnabled } from "./db/database.js";
import { startWorkerRuntime } from "./runtime/workerRuntime.js";

async function main() {
  assertDatabaseConfigured();
  if (isDbEnabled()) {
    await ensureDatabaseReady();
  }
  startWorkerRuntime();
}

main().catch((err) => {
  console.error("[worker] failed to start", err);
  process.exit(1);
});
