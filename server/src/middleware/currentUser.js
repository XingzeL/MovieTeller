import { getSessionCookieValue } from "./parseCookies.js";
import {
  isClerkConfigured,
  resolveClerkUserIdFromBearer,
} from "./clerkBearer.js";
import {
  isProductionEnv,
  normalizeAuthUserId,
  normalizeUserId,
} from "./userId.js";

const DEV_USER_HEADER = "x-movieteller-user-id";

/**
 * @param {import('express').Request} req
 */
function hasBearerAuthHeader(req) {
  const header = req.headers.authorization;
  return typeof header === "string" && /^Bearer\s+/i.test(header);
}

/**
 * @param {import('express').Request} req
 * @returns {Promise<string | null>}
 */
export async function resolveUserId(req) {
  const clerkRaw = await resolveClerkUserIdFromBearer(req);
  const fromClerk = normalizeAuthUserId(clerkRaw);
  if (fromClerk) return fromClerk;

  if (isClerkConfigured() && hasBearerAuthHeader(req)) {
    return null;
  }

  if (isProductionEnv()) {
    return null;
  }

  const fromCookie = normalizeUserId(getSessionCookieValue(req));
  if (fromCookie) return fromCookie;

  const headerVal = req.headers[DEV_USER_HEADER];
  const fromHeader = normalizeUserId(
    Array.isArray(headerVal) ? headerVal[0] : headerVal
  );
  if (fromHeader) return fromHeader;

  const bypass = normalizeUserId(process.env.CLERK_BYPASS_USER_ID?.trim());
  if (bypass) return bypass;

  return null;
}

/**
 * @param {import('express').Request} req
 * @param {import('express').Response} res
 * @param {import('express').NextFunction} next
 */
export async function currentUserOptional(req, _res, next) {
  try {
    const id = await resolveUserId(req);
    req.user = id ? { id } : null;
    next();
  } catch (err) {
    next(err);
  }
}

/**
 * @param {import('express').Request} req
 * @param {import('express').Response} res
 * @param {import('express').NextFunction} next
 */
export async function requireCurrentUser(req, res, next) {
  try {
    const id = await resolveUserId(req);
    if (!id) {
      return res.status(401).json({ error: "unauthorized" });
    }
    req.user = { id };
    next();
  } catch (err) {
    next(err);
  }
}
