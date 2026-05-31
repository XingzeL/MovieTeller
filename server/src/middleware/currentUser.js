import { getSessionCookieValue } from "./parseCookies.js";
import { getDemoUserId, normalizeUserId } from "./userId.js";

const DEV_USER_HEADER = "x-movieteller-user-id";

/**
 * Resolve current user id: cookie → (non-prod) header → demo default.
 * @param {import('express').Request} req
 * @returns {string}
 */
export function resolveUserId(req) {
  const fromCookie = normalizeUserId(getSessionCookieValue(req));
  if (fromCookie) return fromCookie;

  if (process.env.NODE_ENV !== "production") {
    const headerVal = req.headers[DEV_USER_HEADER];
    const fromHeader = normalizeUserId(
      Array.isArray(headerVal) ? headerVal[0] : headerVal
    );
    if (fromHeader) return fromHeader;
  }

  return getDemoUserId();
}

/**
 * @param {import('express').Request} req
 * @param {import('express').Response} res
 * @param {import('express').NextFunction} next
 */
export function currentUserMiddleware(req, _res, next) {
  const id = resolveUserId(req);
  req.user = { id };
  next();
}
