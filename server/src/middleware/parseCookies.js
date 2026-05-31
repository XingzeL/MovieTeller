/**
 * Minimal Cookie header parser (no cookie-parser dependency).
 * @param {string | undefined} header
 * @returns {Record<string, string>}
 */
export function parseCookies(header) {
  const out = {};
  if (!header || typeof header !== "string") return out;

  for (const part of header.split(";")) {
    const idx = part.indexOf("=");
    if (idx <= 0) continue;
    const name = part.slice(0, idx).trim();
    const value = part.slice(idx + 1).trim();
    if (!name) continue;
    try {
      out[name] = decodeURIComponent(value);
    } catch {
      out[name] = value;
    }
  }
  return out;
}

export const SESSION_COOKIE_NAME = "mt_uid";

/**
 * @param {import('express').Request} req
 * @returns {string | undefined}
 */
export function getSessionCookieValue(req) {
  const cookies = parseCookies(req.headers.cookie);
  return cookies[SESSION_COOKIE_NAME];
}
