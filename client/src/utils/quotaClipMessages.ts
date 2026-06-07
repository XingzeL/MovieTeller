export type QuotaClipReason = {
  code: string
  category: 'plan_limit' | 'quota_insufficient'
  limitSeconds: number
  limitMinutes: number
}

function formatDurationZh(seconds: number) {
  const minutes = Math.floor(seconds / 60)
  const secs = seconds % 60
  if (minutes <= 0) return `${secs} 秒`
  if (secs === 0) return `${minutes} 分钟`
  return `${minutes} 分 ${secs} 秒`
}

function formatDurationEn(seconds: number) {
  const minutes = Math.floor(seconds / 60)
  const secs = seconds % 60
  if (minutes <= 0) return `${secs}s`
  if (secs === 0) return `${minutes} min`
  return `${minutes}m ${secs}s`
}

export function quotaClipReasonMessage(
  reason: QuotaClipReason,
  lang: 'zh' | 'en',
): string {
  const limit =
    lang === 'zh'
      ? formatDurationZh(reason.limitSeconds)
      : formatDurationEn(reason.limitSeconds)

  if (lang === 'zh') {
    switch (reason.code) {
      case 'plan_max_video':
        return `当前套餐单次视频最长 ${limit}，原视频更长，因此只处理前 ${limit}。`
      case 'daily_processing_quota':
        return `今日剩余处理额度约 ${limit}，无法处理完整视频。`
      case 'processing_quota':
        return `基础处理额度剩余约 ${limit}，不足以覆盖完整视频。`
      case 'narration_quota':
        return `解说额度剩余约 ${limit}；可关闭「生成解说声道」后重试，或购买额度包。`
      default:
        return `受额度或套餐限制，最多处理 ${limit}。`
    }
  }

  switch (reason.code) {
    case 'plan_max_video':
      return `Your plan allows up to ${limit} per video; only the first ${limit} will be processed.`
    case 'daily_processing_quota':
      return `Only about ${limit} of daily processing quota remains today.`
    case 'processing_quota':
      return `Only about ${limit} of processing quota remains for this billing period.`
    case 'narration_quota':
      return `Only about ${limit} of narration quota remains. Disable narrated audio or buy a quota pack.`
    default:
      return `Processing is limited to about ${limit} due to quota or plan rules.`
  }
}

export function buildQuotaClipNotice(input: {
  lang: 'zh' | 'en'
  sourceDurationSec: number
  processedDurationSec: number
  reasons: QuotaClipReason[]
}) {
  const format =
    input.lang === 'zh' ? formatDurationZh : formatDurationEn
  const title =
    input.lang === 'zh' ? '视频将被裁剪' : 'Your video will be trimmed'
  const intro =
    input.lang === 'zh'
      ? `原视频时长 ${format(input.sourceDurationSec)}，实际将处理 ${format(input.processedDurationSec)}。`
      : `Source length is ${format(input.sourceDurationSec)}; we will process ${format(input.processedDurationSec)}.`
  const reasonLines =
    input.reasons.length > 0
      ? input.reasons.map((reason) => quotaClipReasonMessage(reason, input.lang))
      : [
          input.lang === 'zh'
            ? '视频时长超过当前额度或套餐限制。'
            : 'The video exceeds your current quota or plan limits.',
        ]
  const footer =
    input.lang === 'zh'
      ? '任务仍会按裁剪后的时长创建并继续处理。'
      : 'The job will still be created and processed using the trimmed duration.'

  return { title, intro, reasonLines, footer }
}
