#!/usr/bin/env node
/**
 * Test/dev runner: marks workflow running and hangs (ignores cancel.flag).
 * Enabled only when spawnWorkflowJob sees MOVIE_TELLER_FAKE_HANGING_RUNNER=1
 * and (NODE_ENV=test or MOVIE_TELLER_ALLOW_FAKE_RUNNER=1).
 */
import fs from "node:fs";
import path from "node:path";

function parseArgs(argv) {
  const out = {};
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "--job-id") out.jobId = argv[++i];
    else if (arg === "--jobs-root") out.jobsRoot = argv[++i];
    else if (arg === "--video") out.video = argv[++i];
    else if (arg === "--request-json") out.requestJson = argv[++i];
    else if (arg === "--user-id") out.userId = argv[++i];
  }
  return out;
}

const opts = parseArgs(process.argv.slice(2));
if (!opts.jobId || !opts.jobsRoot) {
  console.error("fake-hanging-runner: --job-id and --jobs-root required");
  process.exit(2);
}

const jobRoot = path.join(opts.jobsRoot, opts.jobId);
const workflowPath = path.join(jobRoot, "workflow.json");
const now = new Date().toISOString();

let record = {};
if (fs.existsSync(workflowPath)) {
  try {
    record = JSON.parse(fs.readFileSync(workflowPath, "utf8"));
  } catch {
    record = {};
  }
}

const next = {
  ...record,
  job_id: opts.jobId,
  status: "running",
  input_video_path: opts.video || record.input_video_path,
  output_root: jobRoot,
  user_id: opts.userId || record.user_id,
  updated_at: now,
  created_at: record.created_at || now,
};
fs.writeFileSync(workflowPath, `${JSON.stringify(next, null, 2)}\n`, "utf8");

process.on("SIGTERM", () => {});
process.on("SIGINT", () => {});

setInterval(() => {}, 60_000);
