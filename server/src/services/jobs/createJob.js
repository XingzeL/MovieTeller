import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";

import {
  getJobsRoot,
  jobPathsFromRoot,
  resolveJobRoot,
} from "../../config/jobs.js";
import { spawnWorkflowJob } from "./spawnWorkflowJob.js";
import { workflowOptionsFromForm } from "./workflowOptions.js";

function utcNowIso() {
  return new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
}

/**
 * @param {{ file: { path: string, originalname?: string }, body: Record<string, unknown>, spawn?: boolean }} input
 */
export function createJobFromUpload(input) {
  const jobsRoot = getJobsRoot();
  const jobId = crypto.randomUUID();
  const jobRoot = resolveJobRoot(jobsRoot, jobId);
  const paths = jobPathsFromRoot(jobRoot);

  for (const dir of [
    paths.inputDir,
    paths.logsDir,
    path.join(jobRoot, "subtitles"),
    path.join(jobRoot, "analysis"),
    path.join(jobRoot, "frame_pool"),
    path.join(jobRoot, "narration"),
    path.join(jobRoot, "speech"),
    path.join(jobRoot, "speech", "audio"),
    path.join(jobRoot, "render"),
    path.join(jobRoot, "study_cards"),
    path.join(jobRoot, "artifacts"),
  ]) {
    fs.mkdirSync(dir, { recursive: true });
  }

  const ext = path.extname(input.file.originalname || "") || ".mp4";
  const destVideo = path.join(paths.inputDir, `source${ext}`);
  fs.renameSync(input.file.path, destVideo);

  const options = workflowOptionsFromForm(input.body);
  fs.writeFileSync(
    paths.requestJsonPath,
    `${JSON.stringify(options, null, 2)}\n`,
    "utf8"
  );

  const now = utcNowIso();
  const userId =
    typeof input.body.userId === "string" && input.body.userId.trim()
      ? input.body.userId.trim()
      : null;

  const shouldSpawn = input.spawn !== false;
  const status = shouldSpawn ? "queued" : "queued";

  const queuedRecord = {
    job_id: jobId,
    status,
    input_video_path: destVideo,
    output_root: paths.root,
    user_id: userId,
    current_stage: null,
    progress: {},
    error: null,
    artifacts: {},
    created_at: now,
    updated_at: now,
  };
  fs.writeFileSync(
    paths.workflowJsonPath,
    `${JSON.stringify(queuedRecord, null, 2)}\n`,
    "utf8"
  );

  if (shouldSpawn) {
    spawnWorkflowJob({
      jobsRoot,
      jobId,
      jobRoot,
      videoPath: destVideo,
      userId,
    });
  }

  return {
    jobId,
    status,
    createdAt: now,
    outputRoot: paths.root,
    videoPath: destVideo,
    userId,
    jobsRoot,
    jobRoot,
  };
}

/**
 * @param {{ jobId: string, jobRoot: string, jobsRoot: string, videoPath: string, userId?: string | null }} prepared
 */
export function spawnPreparedJob(prepared) {
  const paths = jobPathsFromRoot(prepared.jobRoot);
  const now = utcNowIso();
  const record = JSON.parse(fs.readFileSync(paths.workflowJsonPath, "utf8"));
  record.status = "queued";
  record.updated_at = now;
  fs.writeFileSync(paths.workflowJsonPath, `${JSON.stringify(record, null, 2)}\n`, "utf8");
  spawnWorkflowJob({
    jobsRoot: prepared.jobsRoot,
    jobId: prepared.jobId,
    jobRoot: prepared.jobRoot,
    videoPath: prepared.videoPath,
    userId: prepared.userId,
  });
}
