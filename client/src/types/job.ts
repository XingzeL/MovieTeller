export type JobStatus =
  | 'queued'
  | 'running'
  | 'succeeded'
  | 'failed'
  | 'canceled'

export type JobDto = {
  jobId: string
  status: JobStatus
  currentStage?: string | null
  progress?: Record<string, unknown>
  error?: Record<string, unknown> | null
  artifacts?: Record<string, unknown>
  createdAt?: string
  updatedAt?: string
  cancelRequestedAt?: string | null
}

export type JobArtifactItem = {
  kind: string
  label: string
  downloadUrl: string
  sizeBytes?: number
}

export type CreateJobResponse = {
  jobId: string
  status: JobStatus
  createdAt: string
}

export type JobListItem = {
  jobId: string
  status: JobStatus
  currentStage?: string | null
  createdAt?: string
  updatedAt?: string
  cancelRequestedAt?: string | null
  inputFileName?: string | null
}

export type JobListResponse = {
  jobs: JobListItem[]
  total: number
  limit: number
  offset: number
}

export type JobLogLine = Record<string, unknown> & { raw?: string }

export type JobLogsResponse = {
  lines: JobLogLine[]
  truncated: boolean
  nextOffset: number
  bytesRead?: number
}
