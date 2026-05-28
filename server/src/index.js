import express from "express";
import cors from "cors";
import { loadConfig } from "./config/index.js";
import generateRouter from "./routes/generate.js";
import extractRouter from "./routes/extract.js";
import jobsRouter from "./routes/jobs.js";
import healthRouter from "./routes/health.js";
import { getJobsRoot } from "./config/jobs.js";
import { recoverJobsOnStartup } from "./services/jobs/jobRecovery.js";

loadConfig();
getJobsRoot();
const recovery = recoverJobsOnStartup();
if (recovery.recovered > 0) {
  console.warn(`Recovered ${recovery.recovered} stale job(s) on startup`);
}

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
