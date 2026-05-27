import express from "express";
import cors from "cors";
import { loadConfig } from "./config/index.js";
import generateRouter from "./routes/generate.js";
import extractRouter from "./routes/extract.js";
import workflowRouter from "./routes/workflow.js";

loadConfig();

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
app.use("/api", workflowRouter);

app.get("/health", (_req, res) => {
  res.json({ ok: true });
});

app.listen(PORT, () => {
  console.log(`Server listening on http://localhost:${PORT}`);
});
