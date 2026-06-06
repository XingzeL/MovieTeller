export type UsageRecordStatus = 'succeeded' | 'failed' | 'canceled'

export type UsageRecord = {
  id: string
  jobId: string
  createdAt: string
  videoName: string | null
  sourceDurationSeconds: number | null
  processedDurationSeconds: number | null
  consumedMinutes: number
  remainingAfter: number | null
  status: UsageRecordStatus
}

export type UsageSummary = {
  remainingMinutes: number
  consumedInPeriod: number
  succeededCount: number
  periodStart: string | null
  periodEnd: string | null
  periodQuotaMinutes: number | null
}

export type UsageResponse = {
  records: UsageRecord[]
  total: number
  limit: number
  offset: number
  summary: UsageSummary
}
