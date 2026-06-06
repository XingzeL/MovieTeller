import { runRetentionCycle } from "./retentionPolicy.js";

const INTERVAL_MS = 5 * 60 * 1000;
const MAX_AGE_DAYS = 3;
const STARTUP_DELAY_MS = 30 * 1000;

/**
 * @param {{ jobsRoot?: string, enabled?: boolean }} [opts]
 */
export function startRetentionScheduler(opts = {}) {
  if (opts.enabled === false) {
    return { stop: () => {} };
  }

  const runPurge = () => {
    runRetentionCycle({
      jobsRoot: opts.jobsRoot,
      maxAgeDays: MAX_AGE_DAYS,
    })
      .then((result) => {
      if (result.videoChecked > 0) {
        console.log(
          `[Retention] Video purge: checked ${result.videoChecked}, attempted ${result.videoPurged}`
        );
      }
      if (result.deleted > 0 || result.dbDeleted > 0) {
        console.log(
          `[Retention] Age-based full purge: disk ${result.deleted}, db ${result.dbDeleted ?? 0}, ledger ${result.ledgerDeleted ?? 0} (scanned ${result.ageScanned}).`
        );
      }
      })
      .catch((err) => {
      console.error("[Retention Scheduler] Error during purge run", err);
    });
  };

  const startupTimer = setTimeout(runPurge, STARTUP_DELAY_MS);
  const intervalTimer = setInterval(runPurge, INTERVAL_MS);

  console.log(
    `[Retention Scheduler] Started. ` +
      `Video (download-once) purge + full job deletion for jobs older than ${MAX_AGE_DAYS} days. ` +
      `Runs every 5 minutes.`
  );

  return {
    stop: () => {
      clearTimeout(startupTimer);
      clearInterval(intervalTimer);
    },
  };
}
