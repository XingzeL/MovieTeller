import { verifyToken } from "@clerk/backend";

/** @type {((req: import('express').Request) => (string | null) | Promise<string | null>) | null} */
let verifyHookForTests = null;

export function isClerkConfigured() {
  return Boolean(process.env.CLERK_SECRET_KEY?.trim());
}

/**
 * Origins allowed in session JWT `azp` (Vite dev + optional env list).
 * @returns {string[]}
 */
export function getClerkAuthorizedParties() {
  const raw = process.env.CLERK_AUTHORIZED_PARTIES?.trim();
  if (raw) {
    return raw
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
  }
  return [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
  ];
}

/**
 * @param {((req: import('express').Request) => (string | null) | Promise<string | null>) | null} fn
 */
export function setClerkVerifyHookForTests(fn) {
  verifyHookForTests = fn;
}

/**
 * @param {import('express').Request} req
 * @returns {Promise<string | null>} raw Clerk user id (sub)
 */
export async function resolveClerkUserIdFromBearer(req) {
  if (verifyHookForTests) {
    return verifyHookForTests(req);
  }
  if (!isClerkConfigured()) return null;

  const header = req.headers.authorization;
  if (!header || typeof header !== "string") return null;
  const match = header.match(/^Bearer\s+(.+)$/i);
  if (!match?.[1]) return null;

  try {
    /** @type {import('@clerk/backend').VerifyTokenOptions} */
    const verifyOpts = {
      secretKey: process.env.CLERK_SECRET_KEY,
    };
    if (process.env.CLERK_AUTHORIZED_PARTIES?.trim()) {
      verifyOpts.authorizedParties = getClerkAuthorizedParties();
    }

    const payload = await verifyToken(match[1].trim(), verifyOpts);
    const sub = payload?.sub;
    return typeof sub === "string" && sub.trim() ? sub.trim() : null;
  } catch (err) {
    if (process.env.NODE_ENV !== "production") {
      const message = err instanceof Error ? err.message : String(err);
      console.warn("[clerk] verifyToken failed:", message);
    }
    return null;
  }
}
