import express from "express";

import { SESSION_COOKIE_NAME } from "../middleware/parseCookies.js";
import { currentUserOptional } from "../middleware/currentUser.js";
import { isValidUserId } from "../middleware/userId.js";

const router = express.Router();

/**
 * Switch demo session user (non-production only).
 * Registered before currentUser on the app — no prior cookie required.
 */
router.post("/dev/session", (req, res) => {
  const userId = req.body?.userId;
  if (!isValidUserId(userId)) {
    return res.status(400).json({
      error: "userId must match /^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/",
    });
  }

  const parts = [
    `${SESSION_COOKIE_NAME}=${encodeURIComponent(userId)}`,
    "Path=/",
    "HttpOnly",
    "SameSite=Lax",
  ];
  if (process.env.NODE_ENV === "production") {
    parts.push("Secure");
  }
  res.setHeader("Set-Cookie", parts.join("; "));
  return res.json({ userId });
});

router.delete("/dev/session", (_req, res) => {
  const parts = [
    `${SESSION_COOKIE_NAME}=`,
    "Path=/",
    "HttpOnly",
    "SameSite=Lax",
    "Max-Age=0",
  ];
  if (process.env.NODE_ENV === "production") {
    parts.push("Secure");
  }
  res.setHeader("Set-Cookie", parts.join("; "));
  return res.json({ cleared: true });
});

router.use(currentUserOptional);

router.get("/dev/whoami", (req, res) => {
  return res.json({ userId: req.user?.id ?? null });
});

export default router;
