import dns from "node:dns/promises";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const DEFAULT_ALLOWLIST = [
  "bilibili.com",
  "b23.tv",
  "douyin.com",
  "iesdouyin.com",
  "vimeo.com",
  "tiktok.com",
];

const UNSUPPORTED_SOURCE_HOSTS = ["youtube.com", "youtu.be"];

/**
 * @param {string} hostname
 */
function isBlockedHostname(hostname) {
  const host = String(hostname || "").toLowerCase().replace(/\.$/, "");
  if (!host) return true;
  if (host === "localhost" || host.endsWith(".localhost")) return true;

  const withoutBrackets =
    host.startsWith("[") && host.endsWith("]") ? host.slice(1, -1) : host;
  if (withoutBrackets === "::1") return true;

  const ipv4Match = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/.exec(
    withoutBrackets
  );
  if (ipv4Match) {
    return isPrivateIpv4(ipv4Match.slice(1).map((p) => Number(p)));
  }

  return false;
}

/**
 * @param {number[]} parts
 */
function isPrivateIpv4(parts) {
  if (parts.some((p) => !Number.isInteger(p) || p < 0 || p > 255)) return true;
  const [a, b] = parts;
  if (a === 127) return true;
  if (a === 10) return true;
  if (a === 172 && b >= 16 && b <= 31) return true;
  if (a === 192 && b === 168) return true;
  if (a === 169 && b === 254) return true;
  if (a === 0) return true;
  return false;
}

/**
 * @param {string} address
 */
function isPrivateIpAddress(address) {
  const normalized = String(address || "").toLowerCase();
  if (!normalized) return true;
  if (normalized === "::1") return true;
  if (normalized.startsWith("fc") || normalized.startsWith("fd")) return true;
  if (normalized.startsWith("fe80:")) return true;

  const ipv4Match = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/.exec(
    normalized
  );
  if (ipv4Match) {
    return isPrivateIpv4(ipv4Match.slice(1).map((p) => Number(p)));
  }
  return false;
}

/**
 * @returns {string[] | null} null = allowlist disabled
 */
export function getSourceUrlAllowlist() {
  const raw = process.env.SOURCE_URL_ALLOWLIST;
  if (raw == null || String(raw).trim() === "") {
    return DEFAULT_ALLOWLIST;
  }
  const trimmed = String(raw).trim();
  if (trimmed === "*" || trimmed.toLowerCase() === "all") {
    return null;
  }
  return trimmed
    .split(",")
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean);
}

/**
 * @param {string} hostname
 * @param {string[] | null} allowlist
 */
export function hostnameMatchesAllowlist(hostname, allowlist) {
  if (!allowlist) return true;
  const host = String(hostname || "").toLowerCase().replace(/\.$/, "");
  return allowlist.some(
    (domain) => host === domain || host.endsWith(`.${domain}`)
  );
}

/**
 * @param {string} hostname
 */
export function isUnsupportedSourceHostname(hostname) {
  const host = String(hostname || "").toLowerCase().replace(/\.$/, "");
  return UNSUPPORTED_SOURCE_HOSTS.some(
    (domain) => host === domain || host.endsWith(`.${domain}`)
  );
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

  if (isUnsupportedSourceHostname(parsed.hostname)) {
    return { ok: false, message: "暂不支持 YouTube 链接，请改用本地 MP4 上传。" };
  }

  const allowlist = getSourceUrlAllowlist();
  if (!hostnameMatchesAllowlist(parsed.hostname, allowlist)) {
    return { ok: false, message: "sourceUrl host is not in the allowed list" };
  }

  return { ok: true, url: parsed.toString() };
}

/**
 * DNS-aware validation for outbound fetch/download.
 * @param {string} url
 */
export async function validateSourceUrlAsync(url) {
  const base = validateSourceUrl(url);
  if (!base.ok) return base;

  let parsed;
  try {
    parsed = new URL(base.url);
  } catch {
    return { ok: false, message: "sourceUrl must be a valid URL" };
  }

  if (isBlockedHostname(parsed.hostname)) {
    return { ok: false, message: "sourceUrl points to a blocked host" };
  }

  try {
    const results = await dns.lookup(parsed.hostname, { all: true });
    for (const entry of results) {
      if (isPrivateIpAddress(entry.address)) {
        return {
          ok: false,
          message: "sourceUrl resolves to a blocked network address",
        };
      }
    }
  } catch {
    return { ok: false, message: "sourceUrl hostname could not be resolved" };
  }

  return { ok: true, url: base.url };
}

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
 * @param {{ maxAgeMs?: number }} [opts]
 */
export function cleanupStaleDownloadDirs(opts = {}) {
  const maxAgeMs = opts.maxAgeMs ?? 24 * 60 * 60 * 1000;
  const tmpRoot = os.tmpdir();
  const cutoff = Date.now() - maxAgeMs;
  let removed = 0;

  let entries;
  try {
    entries = fs.readdirSync(tmpRoot, { withFileTypes: true });
  } catch {
    return { removed };
  }

  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    if (!entry.name.startsWith("movieteller_dl_")) continue;
    const fullPath = path.join(tmpRoot, entry.name);
    try {
      const stat = fs.statSync(fullPath);
      if (stat.mtimeMs < cutoff) {
        fs.rmSync(fullPath, { recursive: true, force: true });
        removed += 1;
      }
    } catch {
      /* ignore */
    }
  }

  return { removed };
}
