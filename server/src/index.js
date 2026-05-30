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
import { listJobs } from "./services/jobs/listJobs.js";

loadConfig();
getJobsRoot();
const recovery = recoverJobsOnStartup();
if (recovery.recovered > 0) {
  console.warn(`Recovered ${recovery.recovered} stale job(s) on startup`);
}

/**
 * 简单的定时清理任务
 * 每 5 分钟扫描一次所有已标记下载但未清理的 Job，尝试删除视频文件
 */
function startVideoPurgeScheduler() {
  const INTERVAL_MS = 5 * 60 * 1000; // 5 分钟

  const runPurge = () => {
    try {
      const { jobs } = listJobs({ limit: 200 }); // 取最近 200 个 job 进行检查

      let checked = 0;
      let purged = 0;

      for (const job of jobs) {
        if (job.videoDownloadedAt && !job.videoPurgedAt) {
          checked++;
          purgeVideoForJob(job.jobId);
          purged++;
        }
      }

      if (checked > 0) {
        console.log(`[Purge Scheduler] Checked ${checked} jobs, purge attempted on ${purged}`);
      }
    } catch (err) {
      console.error('[Purge Scheduler] Error during purge run', err);
    }
  };

  // 启动后延迟 30 秒第一次执行，避免启动时压力
  setTimeout(runPurge, 30 * 1000);

  setInterval(runPurge, INTERVAL_MS);

  console.log(`[Purge Scheduler] Started. Will scan for purgeable videos every 5 minutes.`);
}

startVideoPurgeScheduler();

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
