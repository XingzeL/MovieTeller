export class PlanQuotaExhaustedError extends Error {
  constructor(message = "plan quota exhausted") {
    super(message);
    this.name = "PlanQuotaExhaustedError";
    this.code = "plan_quota_exhausted";
    this.statusCode = 400;
  }
}

export class VideoProbeError extends Error {
  constructor(message = "video probe failed") {
    super(message);
    this.name = "VideoProbeError";
    this.code = "video_probe_failed";
    this.statusCode = 400;
  }
}

/**
 * @param {import('express').Response} res
 * @param {unknown} err
 * @returns {boolean} true if handled
 */
export function respondBillingError(res, err) {
  if (!err || typeof err !== "object") return false;
  const statusCode = "statusCode" in err ? Number(err.statusCode) : 0;
  if (statusCode === 400 && "code" in err) {
    res.status(400).json({
      error: String(err.message || err),
      code: String(err.code),
    });
    return true;
  }
  return false;
}
