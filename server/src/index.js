import { startBootstrapRuntime } from "./runtime/bootstrap.js";

startBootstrapRuntime().catch((err) => {
  console.error("[bootstrap] failed to start", err);
  process.exit(1);
});
