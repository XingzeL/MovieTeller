import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

import { clearJobQueueForTests } from "../src/services/jobs/jobQueue.js";
import { createApp } from "../src/app.js";
import { jobPathsFromRoot } from "../src/config/jobs.js";
import { startTestServer } from "./testServer.js";

const repoRoot = path.resolve(process.cwd(), "..");

/**
 * @param {string} root
 * @param {string} jobId
 * @param {Record<string, unknown>} [overrides]
 */
function writeJobFixture(root, jobId, overrides = {}) {
  const jobRoot = path.join(root, jobId);
  const paths = jobPathsFromRoot(jobRoot);
  fs.mkdirSync(paths.inputDir, { recursive: true });
  fs.mkdirSync(paths.logsDir, { recursive: true });
  fs.mkdirSync(path.join(jobRoot, "study_cards"), { recursive: true });
  fs.mkdirSync(path.join(jobRoot, "render"), { recursive: true });
  const studyPath = path.join(jobRoot, "study_cards", "study_cards.html");
  const videoPath = path.join(jobRoot, "render", "narrated.mp4");
  fs.writeFileSync(studyPath, "<html><body>study</body></html>");
  fs.writeFileSync(videoPath, "video");
  const record = {
    job_id: jobId,
    status: "succeeded",
    user_id: "user-a",
    input_video_path: path.join(paths.inputDir, "source.mp4"),
    output_root: jobRoot,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    artifacts: {},
    ...overrides,
  };
  fs.writeFileSync(paths.workflowJsonPath, `${JSON.stringify(record, null, 2)}\n`);
  fs.mkdirSync(path.dirname(paths.artifactManifestPath), { recursive: true });
  fs.writeFileSync(
    paths.artifactManifestPath,
    `${JSON.stringify(
      [
        {
          kind: "renderedVideo",
          label: "Rendered video",
          path: videoPath,
          mediaType: "video/mp4",
        },
        {
          kind: "studyCardsHtml",
          label: "Study cards",
          path: studyPath,
          mediaType: "text/html",
        },
      ],
      null,
      2
    )}\n`
  );
  fs.writeFileSync(
    path.join(jobRoot, "request.json"),
    `${JSON.stringify({ enableSpeech: true, enableEmbedVideo: true }, null, 2)}\n`
  );
  fs.writeFileSync(
    paths.workflowLogPath,
    `${JSON.stringify({ event: "workflow.done" })}\n`
  );
  fs.writeFileSync(path.join(paths.inputDir, "source.mp4"), "fake-video");
  return { jobRoot, paths, studyPath, videoPath };
}

/**
 * @param {string} baseUrl
 * @param {string} cookie
 * @param {string} reqPath
 * @param {RequestInit} [init]
 */
async function fetchAsUser(baseUrl, cookie, reqPath, init = {}) {
  const headers = new Headers(init.headers);
  headers.set("Cookie", cookie);
  return fetch(`${baseUrl}${reqPath}`, { ...init, headers });
}

test("cross-user cannot access job APIs", async (t) => {
  const root = fs.mkdtempSync(path.join(repoRoot, "artifacts", "test-jobs-"));
  process.env.JOBS_ROOT = root;
  clearJobQueueForTests();

  const jobId = "acl-job-owned-by-a";
  writeJobFixture(root, jobId);

  const app = createApp({ includeDevRoutes: true });
  const { baseUrl, close } = await startTestServer(app);
  t.after(async () => {
    await close();
    fs.rmSync(root, { recursive: true, force: true });
    delete process.env.JOBS_ROOT;
    clearJobQueueForTests();
  });

  const cookieB = "mt_uid=user-b";
  const paths = [
    `/api/jobs/${jobId}`,
    `/api/jobs/${jobId}/progress`,
    `/api/jobs/${jobId}/logs?limit=10`,
    `/api/jobs/${jobId}/artifacts`,
    `/api/jobs/${jobId}/thumbnail`,
    `/api/jobs/${jobId}/artifacts/studyCardsHtml?inline=1`,
    `/api/jobs/${jobId}/artifacts/renderedVideo`,
  ];

  for (const p of paths) {
    const res = await fetchAsUser(baseUrl, cookieB, p);
    assert.equal(res.status, 404, `expected 404 for ${p}`);
  }

  const cancel = await fetchAsUser(baseUrl, cookieB, `/api/jobs/${jobId}/cancel`, {
    method: "POST",
  });
  assert.equal(cancel.status, 404);

  const retry = await fetchAsUser(baseUrl, cookieB, `/api/jobs/${jobId}/retry`, {
    method: "POST",
  });
  assert.equal(retry.status, 404);

  const list = await fetchAsUser(baseUrl, cookieB, "/api/jobs?limit=100");
  const listBody = await list.json();
  assert.equal(listBody.jobs.length, 0);
});

test("owner can access job APIs", async (t) => {
  const root = fs.mkdtempSync(path.join(repoRoot, "artifacts", "test-jobs-"));
  process.env.JOBS_ROOT = root;
  clearJobQueueForTests();

  const jobId = "acl-job-a-ok";
  writeJobFixture(root, jobId);

  const app = createApp({ includeDevRoutes: true });
  const { baseUrl, close } = await startTestServer(app);
  t.after(async () => {
    await close();
    fs.rmSync(root, { recursive: true, force: true });
    delete process.env.JOBS_ROOT;
    clearJobQueueForTests();
  });

  const cookieA = "mt_uid=user-a";

  const detail = await fetchAsUser(baseUrl, cookieA, `/api/jobs/${jobId}`);
  assert.equal(detail.status, 200);
  const detailBody = await detail.json();
  assert.equal(detailBody.job.userId, "user-a");

  const progress = await fetchAsUser(baseUrl, cookieA, `/api/jobs/${jobId}/progress`);
  assert.equal(progress.status, 200);

  const logs = await fetchAsUser(baseUrl, cookieA, `/api/jobs/${jobId}/logs?limit=10`);
  assert.equal(logs.status, 200);

  const artifacts = await fetchAsUser(baseUrl, cookieA, `/api/jobs/${jobId}/artifacts`);
  assert.equal(artifacts.status, 200);

  const thumb = await fetchAsUser(baseUrl, cookieA, `/api/jobs/${jobId}/thumbnail`);
  assert.ok(thumb.status === 200 || thumb.status === 404);

  const inline = await fetchAsUser(
    baseUrl,
    cookieA,
    `/api/jobs/${jobId}/artifacts/studyCardsHtml?inline=1`
  );
  assert.equal(inline.status, 200);
});

test("owner video download marks workflow and writes audit event", async (t) => {
  const root = fs.mkdtempSync(path.join(repoRoot, "artifacts", "test-jobs-"));
  process.env.JOBS_ROOT = root;
  clearJobQueueForTests();

  const jobId = "acl-video-download";
  const { paths } = writeJobFixture(root, jobId);

  const app = createApp({ includeDevRoutes: true });
  const { baseUrl, close } = await startTestServer(app);
  t.after(async () => {
    await close();
    fs.rmSync(root, { recursive: true, force: true });
    delete process.env.JOBS_ROOT;
    clearJobQueueForTests();
  });

  const res = await fetchAsUser(
    baseUrl,
    "mt_uid=user-a",
    `/api/jobs/${jobId}/artifacts/renderedVideo`
  );
  assert.equal(res.status, 200);
  await res.arrayBuffer();

  const workflow = JSON.parse(fs.readFileSync(paths.workflowJsonPath, "utf8"));
  assert.ok(workflow.video_downloaded_at);
  assert.equal(workflow.video_state_version, 1);

  const auditPath = path.join(paths.logsDir, "audit.jsonl");
  const auditLines = fs.readFileSync(auditPath, "utf8").trim().split("\n");
  const events = auditLines.map((line) => JSON.parse(line));
  assert.ok(events.some((event) => event.event === "job.video_downloaded"));
});

test("owner cannot inline preview rendered video", async (t) => {
  const root = fs.mkdtempSync(path.join(repoRoot, "artifacts", "test-jobs-"));
  process.env.JOBS_ROOT = root;
  clearJobQueueForTests();

  const jobId = "acl-video-inline-disabled";
  writeJobFixture(root, jobId);

  const app = createApp({ includeDevRoutes: true });
  const { baseUrl, close } = await startTestServer(app);
  t.after(async () => {
    await close();
    fs.rmSync(root, { recursive: true, force: true });
    delete process.env.JOBS_ROOT;
    clearJobQueueForTests();
  });

  const res = await fetchAsUser(
    baseUrl,
    "mt_uid=user-a",
    `/api/jobs/${jobId}/artifacts/renderedVideo?inline=true`
  );
  assert.equal(res.status, 410);
});

test("owner cannot download rendered video after it was already downloaded", async (t) => {
  const root = fs.mkdtempSync(path.join(repoRoot, "artifacts", "test-jobs-"));
  process.env.JOBS_ROOT = root;
  clearJobQueueForTests();

  const jobId = "acl-video-already-downloaded";
  writeJobFixture(root, jobId, {
    video_downloaded_at: "2026-01-01T00:00:01Z",
    video_state_version: 1,
  });

  const app = createApp({ includeDevRoutes: true });
  const { baseUrl, close } = await startTestServer(app);
  t.after(async () => {
    await close();
    fs.rmSync(root, { recursive: true, force: true });
    delete process.env.JOBS_ROOT;
    clearJobQueueForTests();
  });

  const res = await fetchAsUser(
    baseUrl,
    "mt_uid=user-a",
    `/api/jobs/${jobId}/artifacts/renderedVideo`
  );
  assert.equal(res.status, 410);
});

test("create job ignores body userId and uses cookie owner", async (t) => {
  const root = fs.mkdtempSync(path.join(repoRoot, "artifacts", "test-jobs-"));
  process.env.JOBS_ROOT = root;
  clearJobQueueForTests();

  const app = createApp({ includeDevRoutes: true });
  const { baseUrl, close } = await startTestServer(app);
  t.after(async () => {
    await close();
    fs.rmSync(root, { recursive: true, force: true });
    delete process.env.JOBS_ROOT;
    clearJobQueueForTests();
  });

  const videoPath = path.join(root, "_upload.mp4");
  fs.writeFileSync(videoPath, "x".repeat(128));

  const form = new FormData();
  const blob = new Blob([fs.readFileSync(videoPath)], { type: "video/mp4" });
  form.append("file", blob, "clip.mp4");
  form.append("userId", "user-b");
  form.append("enableSpeech", "false");

  const created = await fetchAsUser(baseUrl, "mt_uid=user-a", "/api/jobs", {
    method: "POST",
    body: form,
  });
  assert.equal(created.status, 201);
  const body = await created.json();
  const jobId = body.jobId;
  assert.ok(jobId);

  const workflow = JSON.parse(
    fs.readFileSync(path.join(root, jobId, "workflow.json"), "utf8")
  );
  assert.equal(workflow.user_id, "user-a");
});

test("jobs without user_id are invisible", async (t) => {
  const root = fs.mkdtempSync(path.join(repoRoot, "artifacts", "test-jobs-"));
  process.env.JOBS_ROOT = root;

  const jobId = "legacy-no-user";
  writeJobFixture(root, jobId, { user_id: undefined });

  const app = createApp({ includeDevRoutes: true });
  const { baseUrl, close } = await startTestServer(app);
  t.after(async () => {
    await close();
    fs.rmSync(root, { recursive: true, force: true });
    delete process.env.JOBS_ROOT;
  });

  for (const user of ["user-a", "user-b"]) {
    const list = await fetchAsUser(baseUrl, `mt_uid=${user}`, "/api/jobs?limit=100");
    const body = await list.json();
    assert.equal(
      body.jobs.find((j) => j.jobId === jobId),
      undefined
    );
  }
});
