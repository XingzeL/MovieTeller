import { isDbEnabled } from "../../db/database.js";
import { scanAllJobsForSystem } from "../jobs/scanAllJobsForSystem.js";
import { purgeVideoForJob } from "../jobs/purgeVideo.js";
import { purgeOldJobs } from "../jobs/purgeOldJobs.js";
import { purgeOldJobsFromDb } from "../jobs/purgeOldJobsFromDb.js";
import { purgeOrphanJobDirectories } from "../jobs/purgeOrphanJobDirectories.js";
import { purgeOldUsageLedger } from "../billing/purgeOldUsageLedger.js";

const RECENT_VIDEO_PURGE_LIMIT = 200;

/**
 * @param {{ jobsRoot?: string, maxAgeDays?: number }} [opts]
 */
export async function runRetentionCycle(opts = {}) {
  const maxAgeDays = opts.maxAgeDays ?? 3;
  const scanned = await scanAllJobsForSystem({ jobsRoot: opts.jobsRoot });

  const recentByUpdated = [...scanned].sort((a, b) => {
    const ta = Date.parse(String(a.listItem.updatedAt || a.listItem.createdAt || ""));
    const tb = Date.parse(String(b.listItem.updatedAt || b.listItem.createdAt || ""));
    return (Number.isFinite(tb) ? tb : 0) - (Number.isFinite(ta) ? ta : 0);
  });

  let videoChecked = 0;
  let videoPurged = 0;

  for (const entry of recentByUpdated.slice(0, RECENT_VIDEO_PURGE_LIMIT)) {
    const job = entry.listItem;
    if (job.videoDownloadedAt && !job.videoPurgedAt) {
      videoChecked++;
      purgeVideoForJob(job.jobId);
      videoPurged++;
    }
  }

  let deleted = 0;
  let ageScanned = 0;
  let dbDeleted = 0;
  let ledgerDeleted = 0;
  let orphansDeleted = 0;

  if (isDbEnabled()) {
    const dbResult = await purgeOldJobsFromDb(maxAgeDays);
    ageScanned = dbResult.scanned;
    deleted = dbResult.diskDeleted;
    dbDeleted = dbResult.dbDeleted;
    const ledgerResult = await purgeOldUsageLedger(maxAgeDays);
    ledgerDeleted = ledgerResult.deleted;
    const orphanResult = await purgeOrphanJobDirectories({ jobsRoot: opts.jobsRoot });
    orphansDeleted = orphanResult.deleted;
  } else {
    const fsResult = await purgeOldJobs(maxAgeDays, { jobsRoot: opts.jobsRoot });
    deleted = fsResult.deleted;
    ageScanned = fsResult.scanned;
  }

  return {
    videoChecked,
    videoPurged,
    deleted,
    ageScanned,
    dbDeleted,
    ledgerDeleted,
    orphansDeleted,
  };
}
