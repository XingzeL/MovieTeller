import { scanAllJobsForSystem } from "../jobs/scanAllJobsForSystem.js";
import { purgeVideoForJob } from "../jobs/purgeVideo.js";
import { purgeOldJobs } from "../jobs/purgeOldJobs.js";

const RECENT_VIDEO_PURGE_LIMIT = 200;

/**
 * @param {{ jobsRoot?: string, maxAgeDays?: number }} [opts]
 */
export function runRetentionCycle(opts = {}) {
  const maxAgeDays = opts.maxAgeDays ?? 3;
  const scanned = scanAllJobsForSystem({ jobsRoot: opts.jobsRoot });

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

  const { deleted, scanned: ageScanned } = purgeOldJobs(maxAgeDays, {
    jobsRoot: opts.jobsRoot,
  });

  return { videoChecked, videoPurged, deleted, ageScanned };
}
