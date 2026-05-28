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
