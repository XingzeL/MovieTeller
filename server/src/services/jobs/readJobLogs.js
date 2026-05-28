import fs from "node:fs";

import { readJobRecord } from "./readJob.js";

const DEFAULT_LIMIT = 500;
const MAX_LIMIT = 5000;
const NEWLINE_BYTE = 10;

function normalizeLimit(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) return DEFAULT_LIMIT;
  return Math.min(Math.floor(parsed), MAX_LIMIT);
}

function normalizeOffset(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < 0) return 0;
  return Math.floor(parsed);
}

function parseLine(line) {
  const text = line.trim();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return { raw: text };
  }
}

/**
 * @param {string} jobId
 * @param {{ limit?: number, after?: number }} [opts]
 */
export function readJobLogs(jobId, opts = {}) {
  const { paths } = readJobRecord(jobId);
  if (!fs.existsSync(paths.workflowLogPath)) {
    return { lines: [], truncated: false, nextOffset: 0, bytesRead: 0 };
  }

  const buffer = fs.readFileSync(paths.workflowLogPath);
  const fileSize = buffer.length;
  const hasCursor = opts.after !== undefined && opts.after !== null;
  const startOffset = hasCursor ? Math.min(normalizeOffset(opts.after), fileSize) : 0;

  if (hasCursor) {
    const limit = normalizeLimit(opts.limit);
    const lines = [];
    let cursor = startOffset;
    while (cursor < fileSize && lines.length < limit) {
      const newlineIdx = buffer.indexOf(NEWLINE_BYTE, cursor);
      const lineEnd = newlineIdx >= 0 ? newlineIdx : fileSize;
      const parsed = parseLine(buffer.subarray(cursor, lineEnd).toString("utf8"));
      cursor = newlineIdx >= 0 ? newlineIdx + 1 : fileSize;
      if (parsed) lines.push(parsed);
    }
    return {
      lines,
      truncated: cursor < fileSize,
      nextOffset: cursor,
      bytesRead: Math.max(0, cursor - startOffset),
    };
  }

  const lines = buffer
    .toString("utf8")
    .split("\n")
    .map(parseLine)
    .filter(Boolean);
  const limit = opts.limit && opts.limit > 0 ? Math.floor(opts.limit) : null;
  if (limit && lines.length > limit) {
    return {
      lines: lines.slice(-limit),
      truncated: true,
      nextOffset: fileSize,
      bytesRead: fileSize,
    };
  }
  return { lines, truncated: false, nextOffset: fileSize, bytesRead: fileSize };
}
