import express from "express";
import cors from "cors";
import { loadConfig } from "./config/index.js";
import generateRouter from "./routes/generate.js";
import extractRouter from "./routes/extract.js";
import jobsRouter from "./routes/jobs.js";
import healthRouter from "./routes/health.js";
import { getJobsRoot } from "./config/jobs.js";
import { recoverJobsOnStartup } from "./services/jobs/jobRecovery.js";
import { purgeVideoForJob } from "./services/jobs/purgeVideo.js";
import { purgeOldJobs } from "./services/jobs/purgeOldJobs.js";
import { listJobs } from "./services/jobs/listJobs.js";

loadConfig();
getJobsRoot();
const recovery = recoverJobsOnStartup();
if (recovery.recovered > 0) {
  console.warn(`Recovered ${recovery.recovered} stale job(s) on startup`);
}

/**
 * 统一的定时保留策略清理任务
 * - 每 5 分钟执行一次
 * - 1. 针对「已下载一次视频」的较新任务，尽快删除其视频文件（原有逻辑）
 * - 2. 删除创建时间超过 3 天的全部旧任务（包含目录下所有文件：视频、学习卡、workflow.json、日志等）
 */
function startRetentionScheduler() {
  const INTERVAL_MS = 5 * 60 * 1000; // 5 分钟
  const MAX_AGE_DAYS = 3;

  const runPurge = () => {
    try {
      // 1. 扫描最近 200 个任务，处理「下载后尽快清理视频」的策略（仅作用于 3 天内的任务）
      const { jobs: recentJobs } = listJobs({ limit: 200 });

      let videoChecked = 0;
      let videoPurged = 0;

      for (const job of recentJobs) {
        if (job.videoDownloadedAt && !job.videoPurgedAt) {
          videoChecked++;
          purgeVideoForJob(job.jobId);
          videoPurged++;
        }
      }

      if (videoChecked > 0) {
        console.log(`[Retention] Video purge: checked ${videoChecked}, attempted ${videoPurged}`);
      }

      // 2. 执行「超过 3 天即彻底删除整个 Job」的保留策略
      const { deleted, scanned } = purgeOldJobs(MAX_AGE_DAYS);

      // purgeOldJobs 内部已有详细日志，这里只在有删除时补充摘要
      if (deleted > 0) {
        console.log(`[Retention] Age-based full purge: deleted ${deleted} jobs older than ${MAX_AGE_DAYS} days (scanned ${scanned} in this cycle).`);
      }
    } catch (err) {
      console.error('[Retention Scheduler] Error during purge run', err);
    }
  };

  // 启动后延迟 30 秒第一次执行，避免启动时压力
  setTimeout(runPurge, 30 * 1000);

  setInterval(runPurge, INTERVAL_MS);

  console.log(
    `[Retention Scheduler] Started. ` +
    `Video (download-once) purge + full job deletion for jobs older than ${MAX_AGE_DAYS} days. ` +
    `Runs every 5 minutes.`
  );
}

startRetentionScheduler();

const PORT = Number(process.env.PORT) || 3001;

const app = express();

app.use(
  cors({
    origin: ["http://localhost:5173", "http://127.0.0.1:5173"],
    methods: ["GET", "POST"],
  })
);

app.use("/api", generateRouter);
app.use("/api", extractRouter);
app.use("/api", jobsRouter);
app.use("/api", healthRouter);

app.get("/health", (_req, res) => {
  res.json({ ok: true });
});

app.listen(PORT, () => {
  console.log(`Server listening on http://localhost:${PORT}`);
});
