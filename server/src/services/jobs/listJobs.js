import fs from "node:fs";
import path from "node:path";

import { getJobsRoot, isSafeJobId, jobPathsFromRoot } from "../../config/jobs.js";
import { readWorkflowRecord } from "./jobProcess.js";
import { readJobRequestMetadata } from "./readJobRequest.js";
import { jobRecordToListItemDto } from "./readJob.js";

const DEFAULT_LIMIT = 20;
const MAX_LIMIT = 1000; // 提高上限，支持前端展示全部历史 + 定时清理扫描

/**
 * @param {unknown} value
 * @param {number} fallback
 */
function parseNonNegativeInt(value, fallback) {
  const n = Number(value);
  if (!Number.isFinite(n) || n < 0) return fallback;
  return Math.floor(n);
}

/**
 * @param {unknown} value
 * @param {number} fallback
 * @param {number} max
 */
function parsePositiveInt(value, fallback, max) {
  const n = Number(value);
  if (!Number.isFinite(n) || n < 1) return fallback;
  return Math.min(Math.floor(n), max);
}

/**
 * @param {string} jobsRoot
 * @returns {Array<{ jobId: string, record: Record<string, unknown>, jobRoot: string }>}
 */
function collectJobRecords(jobsRoot) {
  if (!fs.existsSync(jobsRoot)) {
    return [];
  }

  const entries = [];
  for (const name of fs.readdirSync(jobsRoot)) {
    if (!isSafeJobId(name)) continue;
    const jobRoot = path.join(jobsRoot, name);
    let stat;
    try {
      stat = fs.statSync(jobRoot);
    } catch {
      continue;
    }
    if (!stat.isDirectory()) continue;

    const paths = jobPathsFromRoot(jobRoot);
    const record = readWorkflowRecord(paths.workflowJsonPath);
    if (!record) continue;
    entries.push({
      jobId: String(record.job_id || name),
      record,
      jobRoot,
    });
  }
  return entries;
}

/**
 * @param {Record<string, unknown>} record
 */
function sortTimestamp(record) {
  const raw = record.updated_at || record.created_at;
  const ms = Date.parse(String(raw || ""));
  return Number.isFinite(ms) ? ms : 0;
}

/**
 * @param {{ jobsRoot?: string, limit?: number, offset?: number }} [opts]
 */
function listJobsFromRecords(sorted, opts = {}) {
  const limit = parsePositiveInt(opts.limit, DEFAULT_LIMIT, MAX_LIMIT);
  const offset = parseNonNegativeInt(opts.offset, 0);
  const total = sorted.length;
  const page = sorted.slice(offset, offset + limit);

  return {
    jobs: page.map(({ record, jobRoot }) =>
      jobRecordToListItemDto(
        record,
        readJobRequestMetadata(jobRoot),
        jobRoot
      )
    ),
    total,
    limit,
    offset,
  };
}

/**
 * @param {{ jobsRoot?: string, limit?: number, offset?: number }} [opts]
 */
export function listJobs(opts = {}) {
  const jobsRoot = opts.jobsRoot || getJobsRoot();
  const sorted = collectJobRecords(jobsRoot).sort(
    (a, b) => sortTimestamp(b.record) - sortTimestamp(a.record)
  );
  return listJobsFromRecords(sorted, opts);
}

/**
 * User-scoped job list (excludes jobs without matching user_id).
 * @param {string} userId
 * @param {{ jobsRoot?: string, limit?: number, offset?: number }} [opts]
 */
export function listJobsForUser(userId, opts = {}) {
  const jobsRoot = opts.jobsRoot || getJobsRoot();
  const sorted = collectJobRecords(jobsRoot)
    .filter(({ record }) => record.user_id === userId)
    .sort((a, b) => sortTimestamp(b.record) - sortTimestamp(a.record));
  return listJobsFromRecords(sorted, opts);
}
