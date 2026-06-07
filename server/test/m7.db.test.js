import assert from "node:assert/strict";
import crypto from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import { createApp } from "../src/app.js";
import { jobPathsFromRoot } from "../src/config/jobs.js";
import { closePool, getPool } from "../src/db/pool.js";
import { runMigrations } from "../src/db/ensure.js";
import { getJobById } from "../src/db/jobsRepository.js";
import { upsertStudyCards } from "../src/db/studyCardsRepository.js";
import { getUserBalance } from "../src/db/balancesRepository.js";
import { reserveQuotaAndInsertJob } from "../src/services/billing/reserveQuota.js";
import { upsertUserOnLogin } from "../src/services/billing/upsertUserOnLogin.js";
import {
  listJobArtifacts,
  resolveArtifactDownload,
} from "../src/services/jobs/artifactManifest.js";
import { buildJobAvailability } from "../src/services/jobs/jobAvailability.js";
import { clearJobQueueForTests } from "../src/services/jobs/jobQueue.js";
import { startTestServer } from "./testServer.js";

const repoRoot = path.resolve(process.cwd(), "..");
const hasDb = Boolean(process.env.DATABASE_URL?.trim());
const describeDb = hasDb ? test : test.skip;

const EXPECTED_MIGRATIONS = [
  "001_jobs.sql",
  "002_jobs_retention_and_duration.sql",
  "003_billing_plans.sql",
  "004_usage_ledger.sql",
  "005_job_study_cards.sql",
  "006_reserved_usage_date.sql",
  "007_dual_quota.sql",
  "008_quota_purchases.sql",
];

const M7_JOB_COLUMNS = [
  "source_duration_sec",
  "processed_duration_sec",
  "quota_clip_applied",
  "quota_policy",
  "reserved_minutes",
  "reserved_usage_date",
  "billing_finalized_at",
  "reserved_processing_minutes",
  "reserved_narration_minutes",
  "narration_required",
];

describeDb("M7 migration schema", async (t) => {
  await runMigrations();

  t.after(async () => {
    await closePool();
  });

  await t.test("runMigrations is idempotent", async () => {
    await runMigrations();
  });

  await t.test("schema_migrations records all expected migrations", async () => {
    const result = await getPool().query(
      "SELECT name FROM schema_migrations ORDER BY name"
    );
    const applied = new Set(result.rows.map((row) => row.name));
    for (const name of EXPECTED_MIGRATIONS) {
      assert.ok(applied.has(name), `missing migration ${name}`);
    }
  });

  await t.test("jobs table has M7 billing and retention columns", async () => {
    const result = await getPool().query(
      `SELECT column_name FROM information_schema.columns
       WHERE table_schema = 'public' AND table_name = 'jobs'`
    );
    const columns = new Set(result.rows.map((row) => row.column_name));
    for (const name of M7_JOB_COLUMNS) {
      assert.ok(columns.has(name), `jobs missing column ${name}`);
    }
  });

  await t.test("plans seed contains four tiers", async () => {
    const result = await getPool().query(
      "SELECT code FROM plans WHERE is_active = true ORDER BY sort_order"
    );
    assert.deepEqual(
      result.rows.map((row) => row.code),
      ["free", "lite", "pro", "max"]
    );
  });

  await t.test("dual quota columns exist", async () => {
    const balanceColumns = new Set(
      (
        await getPool().query(
          `SELECT column_name FROM information_schema.columns
           WHERE table_schema = 'public' AND table_name = 'user_balances'`
        )
      ).rows.map((row) => row.column_name)
    );
    assert.ok(balanceColumns.has("narration_remaining_minutes"));
    assert.ok(balanceColumns.has("narration_reserved_minutes"));
    assert.ok(balanceColumns.has("narration_period_quota_minutes"));

    const ledgerColumns = new Set(
      (
        await getPool().query(
          `SELECT column_name FROM information_schema.columns
           WHERE table_schema = 'public' AND table_name = 'usage_ledger'`
        )
      ).rows.map((row) => row.column_name)
    );
    assert.ok(ledgerColumns.has("processing_consumed_minutes"));
    assert.ok(ledgerColumns.has("narration_consumed_minutes"));
    assert.ok(ledgerColumns.has("narration_remaining_after"));
  });

  await t.test("006 reserved_usage_date ALTER is idempotent", async () => {
    const sql = fs.readFileSync(
      path.resolve(process.cwd(), "db/migrations/006_reserved_usage_date.sql"),
      "utf8"
    );
    await getPool().query(sql);
    await getPool().query(sql);
  });
});

describeDb("M7 integration (Postgres)", async (t) => {
  await runMigrations();

  t.after(async () => {
    await closePool();
  });

  await t.test("studyCardsHtml lists and inlines from DB when disk manifest is missing", async () => {
    const userId = `m7-study-db-${crypto.randomUUID()}`;
    const jobId = crypto.randomUUID();
    const artifactsDir = path.join(repoRoot, "artifacts");
    fs.mkdirSync(artifactsDir, { recursive: true });
    const jobsRoot = fs.mkdtempSync(path.join(artifactsDir, "mt-m7-study-"));
    const jobRoot = path.join(jobsRoot, jobId);
    const videoPath = path.join(jobRoot, "input", "source.mp4");
    const paths = jobPathsFromRoot(jobRoot);
    const html = "<html><body>db-only study cards</body></html>";
    const prevJobsRoot = process.env.JOBS_ROOT;
    process.env.JOBS_ROOT = jobsRoot;

    t.after(async () => {
      await cleanupM7Job(userId, jobId);
      fs.rmSync(jobsRoot, { recursive: true, force: true });
      if (prevJobsRoot === undefined) delete process.env.JOBS_ROOT;
      else process.env.JOBS_ROOT = prevJobsRoot;
    });

    fs.mkdirSync(path.dirname(videoPath), { recursive: true });
    fs.writeFileSync(videoPath, "fake-video");
    fs.mkdirSync(paths.logsDir, { recursive: true });
    fs.writeFileSync(
      paths.workflowJsonPath,
      `${JSON.stringify(
        {
          job_id: jobId,
          user_id: userId,
          status: "succeeded",
          input_video_path: videoPath,
          output_root: jobRoot,
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-02T00:00:00Z",
        },
        null,
        2
      )}\n`
    );
    fs.writeFileSync(
      paths.requestJsonPath,
      `${JSON.stringify({ enableSpeech: true }, null, 2)}\n`
    );

    await upsertUserOnLogin(userId);
    await reserveQuotaAndInsertJob({
      jobId,
      userId,
      outputRoot: jobRoot,
      inputVideoPath: videoPath,
      sourceDurationSec: 60,
    });
    await getPool().query(
      `UPDATE jobs SET status = 'succeeded', completed_at = now(), updated_at = now()
       WHERE job_id = $1`,
      [jobId]
    );
    await upsertStudyCards({ jobId, html });

    assert.equal(fs.existsSync(paths.artifactManifestPath), false);

    const artifacts = await listJobArtifacts(jobId);
    const study = artifacts.find((item) => item.kind === "studyCardsHtml");
    assert.ok(study, "expected studyCardsHtml in artifact list");

    const resolved = await resolveArtifactDownload(jobId, "studyCardsHtml");
    assert.equal(resolved.html, html);

    const availability = await buildJobAvailability(
      await getJobById(jobId),
      { enableSpeech: true },
      jobRoot
    );
    assert.equal(availability.canOpenStudyCards, true);

    const app = createApp({ includeDevRoutes: true });
    const { baseUrl, close } = await startTestServer(app);
    try {
      const res = await fetch(
        `${baseUrl}/api/jobs/${jobId}/artifacts/studyCardsHtml?inline=1`,
        { headers: { Cookie: `mt_uid=${userId}` } }
      );
      assert.equal(res.status, 200);
      const body = await res.text();
      assert.match(body, /db-only study cards/);
    } finally {
      await close();
    }
  });

  await t.test("api mode queued cancel finalizes billing and releases reservation", async () => {
    const userId = `m7-cancel-api-${crypto.randomUUID()}`;
    const jobId = crypto.randomUUID();
    const artifactsDir = path.join(repoRoot, "artifacts");
    fs.mkdirSync(artifactsDir, { recursive: true });
    const jobsRoot = fs.mkdtempSync(path.join(artifactsDir, "mt-m7-cancel-"));
    const jobRoot = path.join(jobsRoot, jobId);
    const videoPath = path.join(jobRoot, "input", "source.mp4");
    const paths = jobPathsFromRoot(jobRoot);
    const prevJobsRoot = process.env.JOBS_ROOT;
    const prevMode = process.env.MOVIE_TELLER_RUN_MODE;
    process.env.JOBS_ROOT = jobsRoot;
    process.env.MOVIE_TELLER_RUN_MODE = "api";
    clearJobQueueForTests();

    t.after(async () => {
      await cleanupM7Job(userId, jobId);
      fs.rmSync(jobsRoot, { recursive: true, force: true });
      clearJobQueueForTests();
      if (prevJobsRoot === undefined) delete process.env.JOBS_ROOT;
      else process.env.JOBS_ROOT = prevJobsRoot;
      if (prevMode === undefined) delete process.env.MOVIE_TELLER_RUN_MODE;
      else process.env.MOVIE_TELLER_RUN_MODE = prevMode;
    });

    fs.mkdirSync(path.dirname(videoPath), { recursive: true });
    fs.writeFileSync(videoPath, "fake-video");
    fs.writeFileSync(
      paths.workflowJsonPath,
      `${JSON.stringify(
        {
          job_id: jobId,
          user_id: userId,
          status: "queued",
          input_video_path: videoPath,
          output_root: jobRoot,
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z",
        },
        null,
        2
      )}\n`
    );
    fs.writeFileSync(
      paths.requestJsonPath,
      `${JSON.stringify({ enableSpeech: false }, null, 2)}\n`
    );

    await upsertUserOnLogin(userId);
    const range = await reserveQuotaAndInsertJob({
      jobId,
      userId,
      outputRoot: jobRoot,
      inputVideoPath: videoPath,
      sourceDurationSec: 120,
    });

    let balance = await getUserBalance(userId);
    assert.equal(balance?.reserved_minutes, range.needMinutes);

    const app = createApp({ includeDevRoutes: true });
    const { baseUrl, close } = await startTestServer(app);
    try {
      const res = await fetch(`${baseUrl}/api/jobs/${jobId}/cancel`, {
        method: "POST",
        headers: { Cookie: `mt_uid=${userId}` },
      });
      assert.equal(res.status, 200);
      const body = await res.json();
      assert.equal(body.status, "canceled");
    } finally {
      await close();
    }

    const row = await getJobById(jobId);
    assert.equal(row?.status, "canceled");
    assert.ok(row?.billing_finalized_at);
    assert.equal(Number(row?.reserved_minutes), 0);

    balance = await getUserBalance(userId);
    assert.equal(balance?.reserved_minutes, 0);
    assert.equal(balance?.remaining_minutes, 5);
  });
});

/**
 * @param {string} userId
 * @param {string} jobId
 */
async function cleanupM7Job(userId, jobId) {
  const pool = getPool();
  await pool.query("DELETE FROM job_study_cards WHERE job_id = $1", [jobId]);
  await pool.query("DELETE FROM usage_ledger WHERE job_id = $1", [jobId]);
  await pool.query("DELETE FROM jobs WHERE job_id = $1", [jobId]);
  await pool.query("DELETE FROM user_daily_usage WHERE user_id = $1", [userId]);
  await pool.query("DELETE FROM user_balances WHERE user_id = $1", [userId]);
  await pool.query("DELETE FROM user_subscriptions WHERE user_id = $1", [userId]);
  await pool.query("DELETE FROM users WHERE id = $1", [userId]);
}
