import {
  getEffectiveMaxVideoDurationSec,
  getNarrationAvailableMinutes,
  getProcessingAvailableMinutes,
} from "../../db/balancesRepository.js";

/**
 * Compute allowed processing window and reservation need.
 * @param {{
 *   sourceDurationSec: number,
 *   enableSpeech?: boolean,
 *   plan: { code?: string, max_video_duration_sec: number, max_daily_minutes?: number | null, quota_minutes_per_month?: number, narration_quota_minutes_per_month?: number },
 *   balance: { remaining_minutes: number, reserved_minutes: number, narration_remaining_minutes?: number, narration_reserved_minutes?: number, bonus_processing_minutes?: number, bonus_narration_minutes?: number, max_video_duration_sec_override?: number | null },
 *   dailyUsage?: { consumed_minutes?: number, reserved_minutes?: number } | null,
 * }} input
 */
export function resolveProcessingRange(input) {
  const sourceDurationSec = Math.max(0, Number(input.sourceDurationSec) || 0);
  const processingAvailableMinutes = getProcessingAvailableMinutes(input.balance);
  const processingAvailableSec = processingAvailableMinutes * 60;

  const enableSpeech = input.enableSpeech !== false;
  const narrationAvailableMinutes = enableSpeech
    ? getNarrationAvailableMinutes(input.balance)
    : Number.POSITIVE_INFINITY;
  const narrationAvailableSec = narrationAvailableMinutes * 60;

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

  const effectiveMaxSec = getEffectiveMaxVideoDurationSec(input.plan, input.balance);
  const planMaxSec = effectiveMaxSec > 0 ? effectiveMaxSec : sourceDurationSec;
  const allowedSec = Math.min(
    sourceDurationSec,
    planMaxSec,
    processingAvailableSec,
    narrationAvailableSec,
    dailyAvailableSec
  );

  const startPoint = 0;
  const endPoint = Math.max(0, Math.floor(allowedSec));
  const processedDurationSec = endPoint - startPoint;
  const needMinutes =
    processedDurationSec > 0 ? Math.ceil(processedDurationSec / 60) : 0;
  const quotaClipApplied = endPoint < sourceDurationSec;
  const { clipReasons, primaryClipReason } = buildClipReasons({
    sourceDurationSec,
    planMaxSec,
    processingAvailableSec,
    narrationAvailableSec,
    dailyAvailableSec,
    enableSpeech,
  });

  const quotaPolicy = {
    planCode: input.plan.code ?? null,
    enableSpeech,
    sourceDurationSec,
    processedDurationSec,
    startPoint,
    endPoint,
    maxVideoDurationSec: planMaxSec,
    maxDailyMinutes: input.plan.max_daily_minutes ?? null,
    processingAvailableMinutes,
    narrationAvailableMinutes: enableSpeech ? narrationAvailableMinutes : null,
    dailyAvailableMinutes:
      input.plan.max_daily_minutes != null
        ? Math.max(0, Number(input.plan.max_daily_minutes) - dailyConsumed - dailyReserved)
        : null,
    quotaClipApplied,
    clipReasons,
    primaryClipReason,
    needMinutes,
    needProcessingMinutes: needMinutes,
    needNarrationMinutes: enableSpeech ? needMinutes : 0,
  };

  return {
    startPoint,
    endPoint,
    processedDurationSec,
    needMinutes,
    needProcessingMinutes: needMinutes,
    needNarrationMinutes: enableSpeech ? needMinutes : 0,
    enableSpeech,
    quotaClipApplied,
    quotaPolicy,
  };
}

/**
 * @param {{
 *   sourceDurationSec: number,
 *   planMaxSec: number,
 *   processingAvailableSec: number,
 *   narrationAvailableSec: number,
 *   dailyAvailableSec: number,
 *   enableSpeech: boolean,
 * }} input
 */
export function buildClipReasons(input) {
  const sourceDurationSec = Math.max(0, Number(input.sourceDurationSec) || 0);

  /** @type {{ code: string, category: 'plan_limit' | 'quota_insufficient', limitSec: number }[]} */
  const candidates = [
    {
      code: "plan_max_video",
      category: "plan_limit",
      limitSec: Number(input.planMaxSec) || 0,
    },
    {
      code: "processing_quota",
      category: "quota_insufficient",
      limitSec: Number(input.processingAvailableSec) || 0,
    },
  ];

  if (input.enableSpeech && Number.isFinite(input.narrationAvailableSec)) {
    candidates.push({
      code: "narration_quota",
      category: "quota_insufficient",
      limitSec: Number(input.narrationAvailableSec) || 0,
    });
  }

  if (Number.isFinite(input.dailyAvailableSec)) {
    candidates.push({
      code: "daily_processing_quota",
      category: "plan_limit",
      limitSec: Number(input.dailyAvailableSec) || 0,
    });
  }

  const clipReasons = candidates
    .filter((item) => item.limitSec + 0.001 < sourceDurationSec)
    .map((item) => ({
      code: item.code,
      category: item.category,
      limitSeconds: Math.floor(item.limitSec),
      limitMinutes: Math.max(1, Math.ceil(item.limitSec / 60)),
    }))
    .sort((a, b) => a.limitSeconds - b.limitSeconds);

  return {
    clipReasons,
    primaryClipReason: clipReasons[0]?.code ?? null,
  };
}
