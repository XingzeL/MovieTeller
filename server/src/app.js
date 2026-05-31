import express from "express";
import cors from "cors";

import { currentUserMiddleware } from "./middleware/currentUser.js";
import generateRouter from "./routes/generate.js";
import extractRouter from "./routes/extract.js";
import jobsRouter from "./routes/jobs.js";
import healthRouter from "./routes/health.js";
import devRouter from "./routes/dev.js";

const CORS_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"];

/**
 * @param {{ includeDevRoutes?: boolean }} [opts]
 */
export function createApp(opts = {}) {
  const includeDevRoutes =
    opts.includeDevRoutes ?? process.env.NODE_ENV !== "production";

  const app = express();

  app.use(
    cors({
      origin: CORS_ORIGINS,
      methods: ["GET", "POST"],
      allowedHeaders: ["Content-Type", "X-MovieTeller-User-Id"],
      credentials: true,
    })
  );

  app.use(express.json({ limit: "1mb" }));

  if (includeDevRoutes) {
    app.use("/api", devRouter);
  }

  app.use("/api", currentUserMiddleware);
  app.use("/api", generateRouter);
  app.use("/api", extractRouter);
  app.use("/api", jobsRouter);
  app.use("/api", healthRouter);

  app.get("/health", (_req, res) => {
    res.json({ ok: true });
  });

  return app;
}
