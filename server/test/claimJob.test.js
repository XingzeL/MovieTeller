import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

import { jobPathsFromRoot } from "../src/config/jobs.js";
import {
  claimAndSpawn,
  releaseClaim,
  tryClaim,
} from "../src/services/jobs/claimJob.js";

const repoRoot = path.resolve(process.cwd(), "..");

test("tryClaim allows only one concurrent claim", () => {
  const root = fs.mkdtempSync(path.join(repoRoot, "artifacts", "test-claim-"));
  const jobRoot = path.join(root, "job-1");
  fs.mkdirSync(jobRoot, { recursive: true });
  fs.writeFileSync(
    path.join(jobRoot, "workflow.json"),
    `${JSON.stringify({ job_id: "job-1", status: "queued" }, null, 2)}\n`
  );

  assert.equal(tryClaim("job-1", jobRoot), true);
  assert.equal(tryClaim("job-1", jobRoot), false);
  releaseClaim(jobRoot);
  assert.equal(tryClaim("job-1", jobRoot), true);
  releaseClaim(jobRoot);
  fs.rmSync(root, { recursive: true, force: true });
});

test("stale lock with dead pid can be stolen", () => {
  const root = fs.mkdtempSync(path.join(repoRoot, "artifacts", "test-claim-"));
  const jobRoot = path.join(root, "job-stale");
  fs.mkdirSync(jobRoot, { recursive: true });
  const paths = jobPathsFromRoot(jobRoot);
  fs.writeFileSync(
    paths.workflowJsonPath,
    `${JSON.stringify({ job_id: "job-stale", status: "queued" }, null, 2)}\n`
  );
  fs.writeFileSync(
    paths.workerLockPath,
    `${JSON.stringify({ pid: 999999999, claimedAt: new Date().toISOString() })}\n`
  );

  assert.equal(tryClaim("job-stale", jobRoot), true);
  releaseClaim(jobRoot);
  fs.rmSync(root, { recursive: true, force: true });
});

test("claimAndSpawn releases lock when spawn fails", () => {
  const root = fs.mkdtempSync(path.join(repoRoot, "artifacts", "test-claim-"));
  const jobId = "job-spawn-fail";
  const jobRoot = path.join(root, jobId);
  fs.mkdirSync(jobRoot, { recursive: true });
  const paths = jobPathsFromRoot(jobRoot);
  fs.writeFileSync(
    paths.workflowJsonPath,
    `${JSON.stringify({ job_id: jobId, status: "queued" }, null, 2)}\n`
  );

  const prev = process.env.MOVIE_TELLER_RUN_MODE;
  process.env.MOVIE_TELLER_RUN_MODE = "api";
  try {
    assert.throws(
      () =>
        claimAndSpawn({
          jobId,
          jobRoot,
          jobsRoot: root,
          videoPath: path.join(jobRoot, "missing.mp4"),
          userId: "user-a",
        }),
      /spawn is disabled/
    );
  } finally {
    if (prev === undefined) delete process.env.MOVIE_TELLER_RUN_MODE;
    else process.env.MOVIE_TELLER_RUN_MODE = prev;
  }

  assert.equal(fs.existsSync(paths.workerLockPath), false);
  fs.rmSync(root, { recursive: true, force: true });
});
