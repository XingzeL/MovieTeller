import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

import { scanAllJobsForSystem } from "../src/services/jobs/scanAllJobsForSystem.js";
import { purgeOldJobs } from "../src/services/jobs/purgeOldJobs.js";

const repoRoot = path.resolve(process.cwd(), "..");

/**
 * @param {string} root
 * @param {string} jobId
 * @param {{ createdAt?: string, status?: string, userId?: string }} [opts]
 */
function writeTerminalJob(root, jobId, opts = {}) {
  const jobRoot = path.join(root, jobId);
  fs.mkdirSync(path.join(jobRoot, "input"), { recursive: true });
  const workflowPath = path.join(jobRoot, "workflow.json");
  const createdAt = opts.createdAt ?? "2026-01-01T00:00:00Z";
  fs.writeFileSync(
    workflowPath,
    `${JSON.stringify(
      {
        job_id: jobId,
        status: opts.status ?? "succeeded",
        user_id: opts.userId ?? "demo-user",
        input_video_path: path.join(jobRoot, "input", "source.mp4"),
        output_root: jobRoot,
        created_at: createdAt,
        updated_at: createdAt,
      },
      null,
      2
    )}\n`
  );
}

test("scanAllJobsForSystem is not capped at listJobs MAX_LIMIT", () => {
  const parent = path.join(repoRoot, "artifacts");
  fs.mkdirSync(parent, { recursive: true });
  const root = fs.mkdtempSync(path.join(parent, "test-jobs-"));
  const count = 1050;
  try {
    for (let i = 0; i < count; i++) {
      writeTerminalJob(root, `scan-cap-${String(i).padStart(5, "0")}`);
    }
    const scanned = scanAllJobsForSystem({ jobsRoot: root });
    assert.equal(scanned.length, count);
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test("purgeOldJobs deletes terminal jobs older than retention via scanAllJobs", () => {
  const parent = path.join(repoRoot, "artifacts");
  fs.mkdirSync(parent, { recursive: true });
  const root = fs.mkdtempSync(path.join(parent, "test-jobs-"));
  try {
    writeTerminalJob(root, "old-job", {
      createdAt: "2020-01-01T00:00:00Z",
      status: "succeeded",
    });
    writeTerminalJob(root, "new-job", {
      createdAt: new Date().toISOString(),
      status: "succeeded",
    });
    writeTerminalJob(root, "running-job", {
      createdAt: "2020-01-01T00:00:00Z",
      status: "running",
    });

    const { deleted, scanned } = purgeOldJobs(3, { jobsRoot: root });
    assert.equal(scanned, 3);
    assert.equal(deleted, 1);
    assert.equal(fs.existsSync(path.join(root, "old-job")), false);
    assert.equal(fs.existsSync(path.join(root, "new-job")), true);
    assert.equal(fs.existsSync(path.join(root, "running-job")), true);
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});
