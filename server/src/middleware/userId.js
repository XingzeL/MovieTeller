/** @type {RegExp} */
export const USER_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/;

/**
 * @param {unknown} value
 * @returns {value is string}
 */
export function isValidUserId(value) {
  return typeof value === "string" && USER_ID_PATTERN.test(value);
}

/**
 * @param {unknown} value
 * @returns {string | null}
 */
export function normalizeUserId(value) {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  return isValidUserId(trimmed) ? trimmed : null;
}

export function getDemoUserId() {
  const raw = process.env.DEMO_USER_ID?.trim();
  if (raw && isValidUserId(raw)) return raw;
  return "demo-user";
}

const AUTH_USER_ID_MAX_LEN = 128;

/**
 * Clerk / IdP user ids (e.g. user_abc). Looser than dev cookie pattern.
 * @param {unknown} value
 * @returns {string | null}
 */
export function normalizeAuthUserId(value) {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  if (!trimmed || trimmed.length > AUTH_USER_ID_MAX_LEN) return null;
  if (/[\s/\\]/.test(trimmed)) return null;
  return trimmed;
}

export function isProductionEnv() {
  return process.env.NODE_ENV === "production";
}
