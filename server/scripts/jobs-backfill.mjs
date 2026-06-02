#!/usr/bin/env node
/**
 * Optional: backfill Postgres jobs rows from existing artifacts/jobs/* on disk.
 * Only migrates directories with workflow.json.user_id set.
 *
 * Usage:
 *   DATABASE_URL=postgresql://... node scripts/jobs-backfill.mjs [--dry-run] [--jobs-root=PATH]
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { runMigrations } from "../src/db/ensure.js";
import { getJobById, insertJobQueued } from "../src/db/jobsRepository.js";
import { closePool } from "../src/db/pool.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "../..");

function parseArgs(argv) {
  let dryRun = false;
  let jobsRoot = process.env.JOBS_ROOT || path.join(repoRoot, "artifacts", "jobs");
  for (const arg of argv) {
    if (arg === "--dry-run") dryRun = true;
    else if (arg.startsWith("--jobs-root=")) jobsRoot = arg.slice("--jobs-root=".length);
  }
  return { dryRun, jobsRoot: path.resolve(jobsRoot) };
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

async function main() {
  const { dryRun, jobsRoot } = parseArgs(process.argv.slice(2));
  if (!process.env.DATABASE_URL?.trim()) {
    console.error("DATABASE_URL is required");
    process.exit(1);
  }
  if (!fs.existsSync(jobsRoot)) {
    console.error(`jobs root not found: ${jobsRoot}`);
    process.exit(1);
  }

  await runMigrations();

  let scanned = 0;
  let inserted = 0;
  let skipped = 0;

  for (const name of fs.readdirSync(jobsRoot)) {
    const jobRoot = path.join(jobsRoot, name);
    if (!fs.statSync(jobRoot).isDirectory()) continue;
    const workflowPath = path.join(jobRoot, "workflow.json");
    if (!fs.existsSync(workflowPath)) continue;
    scanned += 1;

    const wf = readJson(workflowPath);
    const userId = typeof wf.user_id === "string" ? wf.user_id.trim() : "";
    if (!userId) {
      skipped += 1;
      continue;
    }

    const jobId = wf.job_id || name;
    const existing = await getJobById(jobId);
    if (existing) {
      skipped += 1;
      continue;
    }

    const inputVideoPath =
      wf.input_video_path || path.join(jobRoot, "input", "source.mp4");
    if (!fs.existsSync(inputVideoPath)) {
      console.warn(`[skip] ${jobId}: missing input video`);
      skipped += 1;
      continue;
    }

    const status = String(wf.status || "queued");
    if (!["queued", "running", "succeeded", "failed", "canceled"].includes(status)) {
      console.warn(`[skip] ${jobId}: unknown status ${status}`);
      skipped += 1;
      continue;
    }

    if (dryRun) {
      console.log(`[dry-run] would insert ${jobId} user=${userId} status=${status}`);
      inserted += 1;
      continue;
    }

    await insertJobQueued({
      jobId,
      userId,
      outputRoot: jobRoot,
      inputVideoPath,
      originalSource: wf.original_source ?? null,
    });

    const pool = (await import("../src/db/pool.js")).getPool();
    await pool.query(
      `UPDATE jobs SET
         status = $2,
         updated_at = COALESCE($3::timestamptz, now()),
         video_downloaded_at = $4,
         video_purged_at = $5,
         video_state_version = COALESCE($6, 0)
       WHERE job_id = $1`,
      [
        jobId,
        status === "running" ? "queued" : status,
        wf.updated_at ?? null,
        wf.video_downloaded_at ?? null,
        wf.video_purged_at ?? null,
        wf.video_state_version ?? 0,
      ]
    );

    console.log(`[insert] ${jobId} (${status} → DB)`);
    inserted += 1;
  }

  console.log(
    `backfill done: scanned=${scanned} inserted=${inserted} skipped=${skipped} dryRun=${dryRun}`
  );
  await closePool();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
