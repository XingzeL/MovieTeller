/**
 * Compute allowed processing window and reservation need.
 * @param {{
 *   sourceDurationSec: number,
 *   plan: { code?: string, max_video_duration_sec: number, max_daily_minutes?: number | null, quota_minutes_per_month?: number },
 *   balance: { remaining_minutes: number, reserved_minutes: number },
 *   dailyUsage?: { consumed_minutes?: number, reserved_minutes?: number } | null,
 * }} input
 */
export function resolveProcessingRange(input) {
  const sourceDurationSec = Math.max(0, Number(input.sourceDurationSec) || 0);
  const remainingMinutes = Number(input.balance.remaining_minutes) || 0;
  const reservedMinutes = Number(input.balance.reserved_minutes) || 0;
  const monthlyAvailableMinutes = Math.max(0, remainingMinutes - reservedMinutes);
  const monthlyAvailableSec = monthlyAvailableMinutes * 60;

  const dailyConsumed = Number(input.dailyUsage?.consumed_minutes) || 0;
  const dailyReserved = Number(input.dailyUsage?.reserved_minutes) || 0;
  let dailyAvailableSec = Number.POSITIVE_INFINITY;
  if (input.plan.max_daily_minutes != null) {
    const dailyRemaining = Math.max(
      0,
      Number(input.plan.max_daily_minutes) - dailyConsumed - dailyReserved
    );
    dailyAvailableSec = dailyRemaining * 60;
  }

  const planMaxSec = Number(input.plan.max_video_duration_sec) || sourceDurationSec;
  const allowedSec = Math.min(
    sourceDurationSec,
    planMaxSec,
    monthlyAvailableSec,
    dailyAvailableSec
  );

  const startPoint = 0;
  const endPoint = Math.max(0, Math.floor(allowedSec));
  const processedDurationSec = endPoint - startPoint;
  const needMinutes =
    processedDurationSec > 0 ? Math.ceil(processedDurationSec / 60) : 0;
  const quotaClipApplied = endPoint < sourceDurationSec;

  const quotaPolicy = {
    planCode: input.plan.code ?? null,
    sourceDurationSec,
    processedDurationSec,
    startPoint,
    endPoint,
    maxVideoDurationSec: planMaxSec,
    maxDailyMinutes: input.plan.max_daily_minutes ?? null,
    monthlyAvailableMinutes,
    dailyAvailableMinutes:
      input.plan.max_daily_minutes != null
        ? Math.max(0, Number(input.plan.max_daily_minutes) - dailyConsumed - dailyReserved)
        : null,
    quotaClipApplied,
    needMinutes,
  };

  return {
    startPoint,
    endPoint,
    processedDurationSec,
    needMinutes,
    quotaClipApplied,
    quotaPolicy,
  };
}
