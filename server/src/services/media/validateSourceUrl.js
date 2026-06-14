/**
 * @param {string} raw
 * @returns {string | null}
 */
export function extractSourceUrl(raw) {
  if (raw == null) return null;
  const trimmed = String(raw).trim();
  return trimmed || null;
}

/**
 * @param {Record<string, unknown> | null | undefined} body
 * @returns {string | null}
 */
export function extractSourceUrlFromBody(body) {
  if (!body || typeof body !== "object") return null;
  const keys = ["sourceUrl", "youtubeUrl", "videoUrl", "remoteUrl"];
  for (const key of keys) {
    const value = extractSourceUrl(body[key]);
    if (value) return value;
  }
  return null;
}

/**
 * @param {string} hostname
 */
function isBlockedHostname(hostname) {
  const host = String(hostname || "").toLowerCase().replace(/\.$/, "");
  if (!host) return true;
  if (host === "localhost" || host.endsWith(".localhost")) return true;

  const withoutBrackets = host.startsWith("[") && host.endsWith("]") ? host.slice(1, -1) : host;
  if (withoutBrackets === "::1") return true;

  const ipv4Match = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/.exec(withoutBrackets);
  if (ipv4Match) {
    const parts = ipv4Match.slice(1).map((p) => Number(p));
    if (parts.some((p) => !Number.isInteger(p) || p < 0 || p > 255)) return true;
    const [a, b] = parts;
    if (a === 127) return true;
    if (a === 10) return true;
    if (a === 172 && b >= 16 && b <= 31) return true;
    if (a === 192 && b === 168) return true;
    if (a === 169 && b === 254) return true;
    if (a === 0) return true;
  }

  return false;
}

/**
 * @param {string} url
 * @returns {{ ok: true, url: string } | { ok: false, message: string }}
 */
export function validateSourceUrl(url) {
  const trimmed = extractSourceUrl(url);
  if (!trimmed) {
    return { ok: false, message: "sourceUrl is required" };
  }

  let parsed;
  try {
    parsed = new URL(trimmed);
  } catch {
    return { ok: false, message: "sourceUrl must be a valid URL" };
  }

  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    return { ok: false, message: "sourceUrl must use http or https" };
  }

  if (isBlockedHostname(parsed.hostname)) {
    return { ok: false, message: "sourceUrl points to a blocked host" };
  }

  return { ok: true, url: parsed.toString() };
}
