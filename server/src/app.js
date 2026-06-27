import express from "express";
import cors from "cors";

import { requireCurrentUser } from "./middleware/currentUser.js";
import generateRouter from "./routes/generate.js";
import extractRouter from "./routes/extract.js";
import jobsRouter from "./routes/jobs.js";
import videosRouter from "./routes/videos.js";
import usageRouter from "./routes/usage.js";
import billingRouter from "./routes/billing.js";
import healthRouter from "./routes/health.js";
import devRouter from "./routes/dev.js";
import { isProductionEnv } from "./middleware/userId.js";

const CORS_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"];

/**
 * @param {{ includeDevRoutes?: boolean }} [opts]
 */
export function createApp(opts = {}) {
  const includeDevRoutes =
    opts.includeDevRoutes ?? !isProductionEnv();

  const app = express();

  const allowedHeaders = isProductionEnv()
    ? ["Content-Type", "Authorization"]
    : ["Content-Type", "Authorization", "X-MovieTeller-User-Id"];

  app.use(
    cors({
      origin: CORS_ORIGINS,
      methods: ["GET", "POST"],
      allowedHeaders,
      credentials: true,
    })
  );

  app.use(express.json({ limit: "1mb" }));

  app.get("/health", (_req, res) => {
    res.json({ ok: true });
  });

  app.use("/api", healthRouter);

  if (includeDevRoutes) {
    app.use("/api", devRouter);
  }

  const protectedApi = express.Router();
  protectedApi.use(requireCurrentUser);
  protectedApi.use(generateRouter);
  protectedApi.use(extractRouter);
  protectedApi.use(videosRouter);
  protectedApi.use(jobsRouter);
  protectedApi.use(usageRouter);
  protectedApi.use(billingRouter);

  app.use("/api", (req, res, next) => {
    if (req.path.startsWith("/healthz")) {
      return next();
    }
    if (req.path.startsWith("/dev")) {
      return next();
    }
    return protectedApi(req, res, next);
  });

  return app;
}
