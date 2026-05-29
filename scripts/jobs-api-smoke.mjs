#!/usr/bin/env node
/**
 * HTTP smoke tests for the Job API (server must already be listening).
 *
 * Examples:
 *   node scripts/jobs-api-smoke.mjs
 *   node scripts/jobs-api-smoke.mjs --mode=create
 *   node scripts/jobs-api-smoke.mjs --mode=cancel --timeout-sec=120
 *   node scripts/jobs-api-smoke.mjs --mode=workflow --timeout-sec=900 --video=/path/to/clip.mp4
 *
 * Env: MOVIE_TELLER_BASE_URL, MOVIE_TELLER_SMOKE_MODE, MOVIE_TELLER_SMOKE_VIDEO,
 *      MOVIE_TELLER_SMOKE_TIMEOUT_SEC
 */
import path from "node:path";
import { fileURLToPath } from "node:url";

import { parseArgs, runSmoke, smokeExit, validateOpts } from "./jobs-api-smoke-lib.mjs";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

async function main() {
  const opts = parseArgs(process.argv.slice(2));
  const check = validateOpts(opts);
  if (!check.ok) {
    if (check.help) {
      console.log(check.help);
      process.exit(0);
    }
    smokeExit(check.error);
  }
  try {
    await runSmoke(opts, { repoRoot });
  } catch (err) {
    smokeExit(err instanceof Error ? err.message : String(err));
  }
}

main();
