import express from "express";
import fs from "node:fs";
import { spawn } from "node:child_process";

import { getJobsRoot } from "../config/jobs.js";
import { loadConfig } from "../config/index.js";
import { resolvePythonRuntime } from "../services/pythonRuntime.js";

const router = express.Router();

function runCommand(cmd, args) {
  return new Promise((resolve) => {
    const child = spawn(cmd, args, { stdio: ["ignore", "pipe", "pipe"] });
    let stderr = "";
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    child.on("close", (code) => resolve({ code, stderr }));
    child.on("error", (err) => resolve({ code: -1, stderr: String(err) }));
  });
}

router.get("/healthz/deep", async (_req, res) => {
  const checks = [];
  const config = loadConfig();
  checks.push({
    name: "config",
    ok: true,
    detail: "loaded",
  });

  const jobsRoot = getJobsRoot();
  try {
    fs.accessSync(jobsRoot, fs.constants.W_OK);
    checks.push({ name: "jobs_root", ok: true, detail: jobsRoot });
  } catch (err) {
    checks.push({
      name: "jobs_root",
      ok: false,
      detail: String(err?.message || err),
    });
  }

  const ffmpeg = await runCommand(config.ffmpeg_path || "ffmpeg", ["-version"]);
  checks.push({
    name: "ffmpeg",
    ok: ffmpeg.code === 0,
    detail: ffmpeg.code === 0 ? "available" : ffmpeg.stderr.slice(0, 200),
  });

  const { python } = resolvePythonRuntime();
  const py = await runCommand(python, ["-m", "movie_pipeline.job_runner", "--help"]);
  checks.push({
    name: "python_job_runner",
    ok: py.code === 0,
    detail: py.code === 0 ? python : py.stderr.slice(0, 200),
  });

  const ok = checks.every((item) => item.ok);
  res.status(ok ? 200 : 503).json({ ok, checks });
});

export default router;
