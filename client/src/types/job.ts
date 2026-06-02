export type JobStatus =
  | 'queued'
  | 'running'
  | 'canceling'
  | 'succeeded'
  | 'failed'
  | 'canceled'

export type VideoState =
  | 'not_generated'
  | 'disabled'
  | 'available'
  | 'downloaded'
  | 'purged'

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
  originalSource?: JobOriginalSource | null
  videoDownloadedAt?: string | null
  videoPurgedAt?: string | null
  videoStateVersion?: number
  /** False when the user did not request TTS / narrated video export. */
  enableSpeech?: boolean
  enableEmbedVideo?: boolean
  videoState?: VideoState
  canDownloadVideo?: boolean
  canOpenStudyCards?: boolean
}

export type JobOriginalSource = {
  type: 'local_upload' | 'remote_url' | 'unknown'
  source_url?: string | null
  original_filename?: string | null
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
  originalSource?: JobOriginalSource | null
  videoDownloadedAt?: string | null
  videoPurgedAt?: string | null
  videoStateVersion?: number
  enableSpeech?: boolean
  enableEmbedVideo?: boolean
  videoState?: VideoState
  canDownloadVideo?: boolean
  canOpenStudyCards?: boolean
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
