import fs from "node:fs";
import path from "node:path";

import { getJobsRoot, isSafeJobId } from "../../config/jobs.js";
import { jobExistsInDb } from "../../db/jobsRepository.js";
import { isDbEnabled } from "../../db/database.js";

/**
 * Remove on-disk job dirs with no Postgres row (low-frequency compensation).
 * @param {{ jobsRoot?: string }} [opts]
 */
export async function purgeOrphanJobDirectories(opts = {}) {
  if (!isDbEnabled()) {
    return { scanned: 0, deleted: 0 };
  }
  const jobsRoot = opts.jobsRoot || getJobsRoot();
  if (!fs.existsSync(jobsRoot)) {
    return { scanned: 0, deleted: 0 };
  }

  let scanned = 0;
  let deleted = 0;

  for (const name of fs.readdirSync(jobsRoot)) {
    if (!isSafeJobId(name)) continue;
    scanned++;
    const exists = await jobExistsInDb(name);
    if (exists) continue;
    const jobRoot = path.join(jobsRoot, name);
    try {
      fs.rmSync(jobRoot, { recursive: true, force: true });
      deleted++;
      console.log(`[Job Retention] Removed orphan directory ${name}`);
    } catch (err) {
      console.error(`[Job Retention] Failed to remove orphan ${name}`, err);
    }
  }

  return { scanned, deleted };
}
