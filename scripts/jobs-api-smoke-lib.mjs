/**
 * Job API smoke helpers (importable from CLI and node:test).
 */
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";

export const TERMINAL = new Set(["succeeded", "failed", "canceled"]);
export const SMOKE_MODES = new Set(["api", "create", "workflow", "cancel"]);

export function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function parseArgs(argv, env = process.env) {
  const opts = {
    baseUrl: (env.MOVIE_TELLER_BASE_URL || "http://localhost:3001").replace(/\/$/, ""),
    mode: env.MOVIE_TELLER_SMOKE_MODE || "api",
    video: env.MOVIE_TELLER_SMOKE_VIDEO || "",
    timeoutSec: Number(env.MOVIE_TELLER_SMOKE_TIMEOUT_SEC || "600"),
    apiPreflight: true,
    strict: env.MOVIE_TELLER_SMOKE_STRICT === "1",
  };
  for (const arg of argv) {
    if (arg.startsWith("--base-url=")) {
      opts.baseUrl = arg.slice("--base-url=".length).replace(/\/$/, "");
    } else if (arg.startsWith("--mode=")) {
      opts.mode = arg.slice("--mode=".length);
    } else if (arg.startsWith("--video=")) {
      opts.video = arg.slice("--video=".length);
    } else if (arg.startsWith("--timeout-sec=")) {
      opts.timeoutSec = Number(arg.slice("--timeout-sec=".length));
    } else if (arg === "--no-api-preflight") {
      opts.apiPreflight = false;
    } else if (arg === "--strict") {
      opts.strict = true;
    } else if (arg === "--help" || arg === "-h") {
      opts.help = true;
    }
  }
  return opts;
}

export function validateOpts(opts) {
  if (opts.help) {
    return {
      ok: false,
      help: `Usage: node scripts/jobs-api-smoke.mjs [--mode=api|create|workflow|cancel] [--base-url=URL] [--video=PATH] [--timeout-sec=N] [--no-api-preflight] [--strict]`,
    };
  }
  if (!SMOKE_MODES.has(opts.mode)) {
    return { ok: false, error: `unknown mode: ${opts.mode}` };
  }
  if (!Number.isFinite(opts.timeoutSec) || opts.timeoutSec < 30) {
    return { ok: false, error: "timeout-sec must be >= 30" };
  }
  return { ok: true };
}

export function fail(message) {
  const err = new Error(message);
  err.isSmokeFail = true;
  throw err;
}

export function smokeExit(message, code = 1) {
  console.error(`FAIL: ${message}`);
  process.exit(code);
}

export function ok(message) {
  console.log(`OK: ${message}`);
}

export async function readJson(res) {
  const text = await res.text();
  try {
    return JSON.parse(text);
  } catch {
    return { raw: text };
  }
}

export async function request(baseUrl, pathname, init = {}) {
  const url = `${baseUrl}${pathname}`;
  const headers = new Headers(init.headers);
  if (
    !headers.has("Authorization") &&
    !headers.has("Cookie") &&
    process.env.MOVIE_TELLER_SMOKE_COOKIE
  ) {
    headers.set("Cookie", process.env.MOVIE_TELLER_SMOKE_COOKIE);
  } else if (!headers.has("Authorization") && !headers.has("Cookie")) {
    headers.set("Cookie", "mt_uid=smoke-user");
  }
  const res = await fetch(url, { ...init, headers });
  const body = await readJson(res);
  return { res, body, url };
}

export function jobDtoFromPollBody(body) {
  return body?.job ?? body;
}

export function formatJobError(job) {
  const err = job?.error;
  if (!err) return "";
  if (typeof err === "string") return err;
  const code = err.error_code || err.errorCode || "";
  const msg = err.message || err.error_message || "";
  return [code, msg].filter(Boolean).join(": ");
}

export function summarizeTerminalJob(job, status) {
  const lines = [
    `jobId=${job?.jobId ?? "?"}`,
    `status=${status}`,
    `stage=${job?.currentStage ?? "?"}`,
  ];
  const errText = formatJobError(job);
  if (errText) lines.push(`error=${errText}`);
  if (job?.cancelRequestedAt) lines.push(`cancelRequestedAt=${job.cancelRequestedAt}`);
  return lines.join(" ");
}

export function ensureSmokeVideo(videoPath, { spawnImpl = spawnSync } = {}) {
  if (videoPath && fs.existsSync(videoPath)) {
    return { path: path.resolve(videoPath), generated: false };
  }
  const tmp = path.join(os.tmpdir(), `movieteller-smoke-${Date.now()}.mp4`);
  const result = spawnImpl(
    "ffmpeg",
    [
      "-y",
      "-hide_banner",
      "-loglevel",
      "error",
      "-f",
      "lavfi",
      "-i",
      "color=c=black:s=160x120:d=1",
      "-t",
      "1",
      "-pix_fmt",
      "yuv420p",
      tmp,
    ],
    { encoding: "utf8" }
  );
  if (result.status !== 0) {
    fail(
      `need --video=PATH or ffmpeg on PATH to generate a 1s clip (${result.stderr || "ffmpeg failed"})`
    );
  }
  return { path: tmp, generated: true };
}

export async function testApiOnly(baseUrl, hooks = {}) {
  const { ok: okFn = ok, fail: failFn = fail, request: req = request } = hooks;

  const health = await req(baseUrl, "/api/healthz/deep");
  if (!health.res.ok || health.body.ok !== true) {
    failFn(`healthz/deep ${health.res.status}: ${JSON.stringify(health.body)}`);
  }
  okFn("healthz/deep");

  const list = await req(baseUrl, "/api/jobs?limit=5&offset=0");
  if (!list.res.ok || !Array.isArray(list.body.jobs)) {
    failFn(`GET /api/jobs ${list.res.status}`);
  }
  okFn(`GET /api/jobs (total=${list.body.total})`);

  const missing = await req(baseUrl, "/api/jobs/00000000-0000-0000-0000-000000000099");
  if (missing.res.status !== 404) {
    failFn(`expected 404 for unknown job, got ${missing.res.status}`);
  }
  okFn("GET unknown job → 404");

  const noFile = await req(baseUrl, "/api/jobs", { method: "POST", body: new FormData() });
  if (noFile.res.status !== 400) {
    failFn(`POST without file expected 400, got ${noFile.res.status}`);
  }
  okFn("POST without file → 400");

  const badPath = path.join(os.tmpdir(), `movieteller-bad-${Date.now()}.txt`);
  fs.writeFileSync(badPath, "not a video");
  const badFd = new FormData();
  badFd.append("file", new Blob([fs.readFileSync(badPath)], { type: "text/plain" }), "bad.txt");
  const badUpload = await req(baseUrl, "/api/jobs", { method: "POST", body: badFd });
  fs.unlinkSync(badPath);
  if (badUpload.res.status !== 400) {
    failFn(`POST bad extension expected 400, got ${badUpload.res.status}`);
  }
  okFn("POST unsupported file → 400");
}

export async function testLogsCursor(baseUrl, jobId, hooks = {}) {
  const { ok: okFn = ok, fail: failFn = fail, request: req = request, sleep: wait = sleep } = hooks;
  let after = 0;
  let totalLines = 0;
  for (let round = 0; round < 3; round += 1) {
    const page = await req(
      baseUrl,
      `/api/jobs/${encodeURIComponent(jobId)}/logs?limit=20&after=${after}`
    );
    if (!page.res.ok) {
      failFn(`logs ${page.res.status}: ${JSON.stringify(page.body)}`);
    }
    if (typeof page.body.nextOffset !== "number") {
      failFn("logs response missing nextOffset");
    }
    totalLines += (page.body.lines || []).length;
    after = page.body.nextOffset;
    await wait(0);
  }
  okFn(`logs cursor (${totalLines} lines across 3 pages, nextOffset=${after})`);
}

export async function createSmokeJob(baseUrl, videoPath, hooks = {}) {
  const { ok: okFn = ok, fail: failFn = fail, request: req = request, ensureVideo = ensureSmokeVideo } =
    hooks;
  const { path: video } = ensureVideo(videoPath);
  const fd = new FormData();
  fd.append("file", new Blob([fs.readFileSync(video)], { type: "video/mp4" }), path.basename(video));
  fd.append("enablePolish", "true");
  fd.append("enableSpeech", "false");
  fd.append("enableSubtitleContext", "true");
  fd.append("enableEmbedVideo", "false");
  fd.append("sourceLanguage", "auto");
  fd.append("cefrLevel", "B1");

  const created = await req(baseUrl, "/api/jobs", { method: "POST", body: fd });
  if (created.res.status !== 201 || !created.body.jobId) {
    failFn(`POST /api/jobs ${created.res.status}: ${JSON.stringify(created.body)}`);
  }
  okFn(`created job ${created.body.jobId}`);
  return created.body.jobId;
}

export async function pollUntilTerminal(baseUrl, jobId, timeoutSec, hooks = {}) {
  const {
    fail: failFn = fail,
    request: req = request,
    sleep: wait = sleep,
    onPoll,
  } = hooks;
  const deadline = Date.now() + timeoutSec * 1000;
  let lastStatus = "unknown";
  let lastJob = null;
  let lastStage = null;
  while (Date.now() < deadline) {
    const { res, body } = await req(baseUrl, `/api/jobs/${encodeURIComponent(jobId)}`);
    if (!res.ok) {
      failFn(`poll job ${res.status}`);
    }
    const job = jobDtoFromPollBody(body);
    lastJob = job;
    lastStatus = job?.status || "unknown";
    const stage = job?.currentStage ?? null;
    if (typeof onPoll === "function") {
      onPoll({ status: lastStatus, stage, job });
    } else if (stage !== lastStage || lastStage === null) {
      console.log(`  poll: status=${lastStatus} stage=${stage ?? "-"}`);
      lastStage = stage;
    }
    if (TERMINAL.has(lastStatus)) {
      return { status: lastStatus, job };
    }
    await wait(2500);
  }
  failFn(`job ${jobId} did not finish within ${timeoutSec}s (last status: ${lastStatus})`);
}

export async function assertArtifactsIfSucceeded(baseUrl, jobId, status, hooks = {}) {
  const { ok: okFn = ok, fail: failFn = fail, request: req = request } = hooks;
  if (status !== "succeeded") {
    okFn(`workflow ended with ${status} (skip artifact manifest check)`);
    return;
  }
  const arts = await req(baseUrl, `/api/jobs/${encodeURIComponent(jobId)}/artifacts`);
  if (!arts.res.ok) {
    failFn(`artifacts ${arts.res.status}`);
  }
  const items = arts.body.artifacts || [];
  if (!Array.isArray(items) || items.length === 0) {
    failFn("succeeded job has no artifacts in API response");
  }
  const kinds = items.map((a) => a.kind);
  okFn(`artifacts (${items.length}): ${kinds.join(", ")}`);
}

export async function testCreate(baseUrl, videoPath, hooks = {}) {
  const jobId = await createSmokeJob(baseUrl, videoPath, hooks);
  const { fail: failFn = fail, request: req = request, ok: okFn = ok } = hooks;

  const listed = await req(baseUrl, "/api/jobs?limit=50&offset=0");
  const found = (listed.body.jobs || []).some((j) => j.jobId === jobId);
  if (!found) {
    failFn("created job not found in GET /api/jobs list");
  }
  okFn("job appears in list");

  const detail = await req(baseUrl, `/api/jobs/${encodeURIComponent(jobId)}`);
  if (!detail.res.ok) {
    failFn(`GET job ${detail.res.status}`);
  }
  const job = jobDtoFromPollBody(detail.body);
  if (!job?.status) {
    failFn("job detail missing status");
  }
  okFn(`job status ${job.status}`);

  await testLogsCursor(baseUrl, jobId, hooks);
  return jobId;
}

export async function testWorkflow(baseUrl, videoPath, timeoutSec, hooks = {}) {
  const { strict = false } = hooks;
  const jobId = await createSmokeJob(baseUrl, videoPath, hooks);
  await testLogsCursor(baseUrl, jobId, hooks);
  const { status, job } = await pollUntilTerminal(baseUrl, jobId, timeoutSec, hooks);
  ok(`terminal status ${status}`);
  console.log(`  ${summarizeTerminalJob(job, status)}`);
  if (strict && status !== "succeeded") {
    fail(
      `strict workflow smoke expected succeeded, got ${status} (${formatJobError(job) || "no error field"})`
    );
  }
  if (status === "failed") {
    ok(`workflow failed (non-strict): check API keys / Python env — ${formatJobError(job) || "see job detail"}`);
  }
  await assertArtifactsIfSucceeded(baseUrl, jobId, status, hooks);
  return { jobId, status, job };
}

export async function testCancel(baseUrl, videoPath, timeoutSec, hooks = {}) {
  const { fail: failFn = fail, request: req = request, ok: okFn = ok } = hooks;
  const jobId = await createSmokeJob(baseUrl, videoPath, hooks);
  const canceled = await req(baseUrl, `/api/jobs/${encodeURIComponent(jobId)}/cancel`, {
    method: "POST",
  });
  if (!canceled.res.ok) {
    failFn(`POST cancel ${canceled.res.status}: ${JSON.stringify(canceled.body)}`);
  }
  const cancelStatus = canceled.body.status;
  if (!["cancel_requested", "canceled", "canceling"].includes(cancelStatus)) {
    failFn(`unexpected cancel response status: ${cancelStatus}`);
  }
  okFn(`POST cancel → ${cancelStatus}`);

  const { status, job } = await pollUntilTerminal(baseUrl, jobId, timeoutSec, hooks);
  console.log(`  ${summarizeTerminalJob(job, status)}`);
  if (status !== "canceled") {
    failFn(`cancel smoke expected canceled, got ${status}`);
  }
  okFn(`terminal status ${status}`);
  return { jobId, status, job };
}

export async function runSmoke(opts, hooks = {}) {
  const {
    ok: okFn = ok,
    fail: failFn = fail,
    testApi = testApiOnly,
    repoRoot = "",
  } = hooks;

  console.log(`smoke baseUrl=${opts.baseUrl} mode=${opts.mode}${repoRoot ? ` repo=${repoRoot}` : ""}`);

  if (opts.apiPreflight) {
    await testApi(opts.baseUrl, hooks);
    if (opts.mode === "api") {
      okFn("api mode complete");
      return;
    }
  }

  if (opts.mode === "create") {
    await testCreate(opts.baseUrl, opts.video, hooks);
    okFn("create mode complete");
    return;
  }
  if (opts.mode === "cancel") {
    await testCancel(opts.baseUrl, opts.video, opts.timeoutSec, hooks);
    okFn("cancel mode complete");
    return;
  }
  if (opts.mode === "workflow") {
    await testWorkflow(opts.baseUrl, opts.video, opts.timeoutSec, {
      ...hooks,
      strict: opts.strict,
    });
    okFn("workflow mode complete");
    return;
  }
  failFn(`unhandled mode ${opts.mode}`);
}
