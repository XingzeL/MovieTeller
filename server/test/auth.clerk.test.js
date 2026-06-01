import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

import { createApp } from "../src/app.js";
import { setClerkVerifyHookForTests } from "../src/middleware/clerkBearer.js";
import { clearJobQueueForTests } from "../src/services/jobs/jobQueue.js";
import { startTestServer } from "./testServer.js";

const repoRoot = path.resolve(process.cwd(), "..");

/**
 * @param {string} baseUrl
 * @param {string} reqPath
 * @param {RequestInit} [init]
 */
async function apiFetch(baseUrl, reqPath, init = {}) {
  return fetch(`${baseUrl}${reqPath}`, init);
}

test("unauthenticated GET /api/jobs returns 401", async (t) => {
  const app = createApp({ includeDevRoutes: true });
  const { baseUrl, close } = await startTestServer(app);
  t.after(() => close());

  const res = await apiFetch(baseUrl, "/api/jobs");
  assert.equal(res.status, 401);
});

test("mock Clerk bearer creates job with auth user_id as owner", async (t) => {
  const root = fs.mkdtempSync(path.join(repoRoot, "artifacts", "test-jobs-"));
  process.env.JOBS_ROOT = root;
  clearJobQueueForTests();

  setClerkVerifyHookForTests((req) => {
    const auth = req.headers.authorization;
    if (auth === "Bearer token-user-a") return "user_clerk_a";
    if (auth === "Bearer token-user-b") return "user_clerk_b";
    return null;
  });

  const app = createApp({ includeDevRoutes: true });
  const { baseUrl, close } = await startTestServer(app);
  t.after(async () => {
    await close();
    setClerkVerifyHookForTests(null);
    fs.rmSync(root, { recursive: true, force: true });
    delete process.env.JOBS_ROOT;
    clearJobQueueForTests();
  });

  const videoPath = path.join(root, "_upload.mp4");
  fs.writeFileSync(videoPath, "x".repeat(128));
  const form = new FormData();
  form.append("file", new Blob([fs.readFileSync(videoPath)]), "clip.mp4");
  form.append("enableSpeech", "false");

  const created = await apiFetch(baseUrl, "/api/jobs", {
    method: "POST",
    headers: { Authorization: "Bearer token-user-a" },
    body: form,
  });
  assert.equal(created.status, 201);
  const body = await created.json();
  const workflowPath = path.join(root, body.jobId, "workflow.json");
  const workflow = JSON.parse(fs.readFileSync(workflowPath, "utf8"));
  assert.equal(workflow.user_id, "user_clerk_a");

  const peek = await apiFetch(baseUrl, `/api/jobs/${body.jobId}`, {
    headers: { Authorization: "Bearer token-user-b" },
  });
  assert.equal(peek.status, 404);
});

test("production ignores X-MovieTeller-User-Id without Bearer", async () => {
  const prev = process.env.NODE_ENV;
  process.env.NODE_ENV = "production";
  try {
    const app = createApp({ includeDevRoutes: false });
    const { baseUrl, close } = await startTestServer(app);
    const res = await fetch(`${baseUrl}/api/jobs`, {
      headers: { "X-MovieTeller-User-Id": "user-a" },
    });
    await close();
    assert.equal(res.status, 401);
  } finally {
    process.env.NODE_ENV = prev;
  }
});

test("health routes stay public without Bearer", async (t) => {
  const app = createApp({ includeDevRoutes: false });
  const { baseUrl, close } = await startTestServer(app);
  t.after(() => close());

  const rootHealth = await fetch(`${baseUrl}/health`);
  assert.equal(rootHealth.status, 200);

  const apiHealth = await fetch(`${baseUrl}/api/healthz/deep`);
  assert.notEqual(apiHealth.status, 401);
});

test("non-production cookie ACL still works without Bearer", async (t) => {
  const root = fs.mkdtempSync(path.join(repoRoot, "artifacts", "test-jobs-"));
  process.env.JOBS_ROOT = root;
  clearJobQueueForTests();
  setClerkVerifyHookForTests(null);

  const jobId = "cookie-only-job";
  const jobRoot = path.join(root, jobId);
  fs.mkdirSync(jobRoot, { recursive: true });
  fs.writeFileSync(
    path.join(jobRoot, "workflow.json"),
    `${JSON.stringify(
      {
        job_id: jobId,
        status: "succeeded",
        user_id: "user-a",
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      },
      null,
      2
    )}\n`
  );

  const app = createApp({ includeDevRoutes: true });
  const { baseUrl, close } = await startTestServer(app);
  t.after(async () => {
    await close();
    fs.rmSync(root, { recursive: true, force: true });
    delete process.env.JOBS_ROOT;
    clearJobQueueForTests();
  });

  const res = await fetch(`${baseUrl}/api/jobs/${jobId}`, {
    headers: { Cookie: "mt_uid=user-a" },
  });
  assert.equal(res.status, 200);
});
