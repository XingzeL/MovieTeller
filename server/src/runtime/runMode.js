/** @typedef {'combined' | 'api' | 'worker'} RunMode */

/**
 * @returns {RunMode}
 */
export function getRunMode() {
  const raw =
    process.env.MOVIE_TELLER_RUN_MODE?.trim() ||
    process.env.RUN_MODE?.trim() ||
    "combined";
  if (raw === "api" || raw === "worker") return raw;
  return "combined";
}

export function isApiRunMode() {
  return getRunMode() === "api";
}

export function isWorkerRunMode() {
  return getRunMode() === "worker";
}

export function isCombinedRunMode() {
  return getRunMode() === "combined";
}
