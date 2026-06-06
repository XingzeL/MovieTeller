import fs from "node:fs";
import path from "node:path";

import { isSafeJobId } from "../../config/jobs.js";
import {
  deleteJobById,
  listEligibleJobsForRetention,
} from "../../db/jobsRepository.js";

/**
 * @param {number} maxAgeDays
 * @returns {Promise<{ scanned: number, diskDeleted: number, dbDeleted: number, diskFailed: number }>}
 */
export async function purgeOldJobsFromDb(maxAgeDays = 3) {
  const eligible = await listEligibleJobsForRetention(maxAgeDays);
  let diskDeleted = 0;
  let dbDeleted = 0;
  let diskFailed = 0;

  for (const row of eligible) {
    const jobId = String(row.job_id);
    if (!isSafeJobId(jobId)) {
      continue;
    }
    const jobRoot = path.resolve(String(row.output_root || ""));

    let diskOk = true;
    if (fs.existsSync(jobRoot)) {
      try {
        fs.rmSync(jobRoot, { recursive: true, force: true });
        diskDeleted++;
      } catch (err) {
        diskOk = false;
        diskFailed++;
        console.error(
          `[Job Retention] Failed to delete job directory ${jobId}`,
          err
        );
      }
    }

    if (!diskOk) {
      continue;
    }

    try {
      const removed = await deleteJobById(jobId);
      if (removed) {
        dbDeleted++;
        console.log(
          `[Job Retention] Deleted job ${jobId} from database (age > ${maxAgeDays} days)`
        );
      }
    } catch (err) {
      console.error(`[Job Retention] Failed to delete job row ${jobId}`, err);
    }
  }

  if (dbDeleted > 0) {
    console.log(
      `[Job Retention] DB purge completed: deleted ${dbDeleted} jobs older than ${maxAgeDays} days (scanned ${eligible.length}).`
    );
  }

  return {
    scanned: eligible.length,
    diskDeleted,
    dbDeleted,
    diskFailed,
  };
}
