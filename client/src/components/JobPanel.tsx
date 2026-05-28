import { useCallback, useEffect, useState } from 'react'

import type { JobArtifactItem, JobDto } from '../types/job'
import { WorkflowProgressBar } from './WorkflowProgressBar'

type Props = {
  jobId: string
  onClear?: () => void
}

export function JobPanel({ jobId, onClear }: Props) {
  const [job, setJob] = useState<JobDto | null>(null)
  const [artifacts, setArtifacts] = useState<JobArtifactItem[]>([])
  const [error, setError] = useState<string | null>(null)

  const fetchJob = useCallback(async () => {
    const res = await fetch(`/api/jobs/${encodeURIComponent(jobId)}`)
    const data = (await res.json()) as { job?: JobDto; error?: string }
    if (!res.ok) {
      throw new Error(data.error ?? `Job request failed (${res.status})`)
    }
    return data.job ?? null
  }, [jobId])

  const fetchArtifacts = useCallback(async () => {
    const res = await fetch(`/api/jobs/${encodeURIComponent(jobId)}/artifacts`)
    const data = (await res.json()) as { artifacts?: JobArtifactItem[]; error?: string }
    if (!res.ok) return []
    return data.artifacts ?? []
  }, [jobId])

  useEffect(() => {
    let cancelled = false
    const tick = async () => {
      try {
        const nextJob = await fetchJob()
        if (cancelled) return
        setJob(nextJob)
        setError(null)
        if (nextJob?.status === 'succeeded') {
          const items = await fetchArtifacts()
          if (!cancelled) setArtifacts(items)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : '无法读取任务状态')
        }
      }
    }
    void tick()
    const id = window.setInterval(() => void tick(), 2500)
    return () => {
      cancelled = true
      window.clearInterval(id)
    }
  }, [fetchArtifacts, fetchJob, jobId])

  const cancelRequested = Boolean(
    (job as { cancelRequestedAt?: string | null } | null)?.cancelRequestedAt
  )

  const terminal =
    job?.status === 'succeeded' ||
    job?.status === 'failed' ||
    job?.status === 'canceled'

  const handleCancel = async () => {
    await fetch(`/api/jobs/${encodeURIComponent(jobId)}/cancel`, { method: 'POST' })
    const nextJob = await fetchJob()
    setJob(nextJob)
  }

  return (
    <div className="mt-6 space-y-4 rounded-xl border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-700 dark:bg-zinc-900/60">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-xs uppercase tracking-wide text-zinc-500">Job</p>
          <p className="font-mono text-sm text-zinc-800 dark:text-zinc-100">{jobId}</p>
        </div>
        <div className="flex gap-2">
          {!terminal && (
            <button
              type="button"
              onClick={() => void handleCancel()}
              className="rounded-lg border border-zinc-300 px-3 py-1.5 text-xs font-medium text-zinc-700 hover:bg-white dark:border-zinc-600 dark:text-zinc-200"
            >
              取消
            </button>
          )}
          {onClear && (
            <button
              type="button"
              onClick={onClear}
              className="rounded-lg border border-zinc-300 px-3 py-1.5 text-xs font-medium text-zinc-700 hover:bg-white dark:border-zinc-600 dark:text-zinc-200"
            >
              新建任务
            </button>
          )}
        </div>
      </div>

      {job && (
        <p className="text-sm text-zinc-600 dark:text-zinc-300">
          状态：<span className="font-medium">{job.status}</span>
          {cancelRequested && job.status !== 'canceled'
            ? ' · 取消已请求'
            : null}
          {job.currentStage ? ` · 阶段 ${job.currentStage}` : null}
        </p>
      )}

      <WorkflowProgressBar jobId={jobId} active={!terminal} />

      {error && (
        <p className="text-sm text-red-700 dark:text-red-300">{error}</p>
      )}

      {job?.error && (
        <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
          {(job.error.message as string) ||
            (job.error.error_message as string) ||
            '任务失败'}
        </p>
      )}

      {artifacts.length > 0 && (
        <div>
          <p className="mb-2 text-sm font-medium text-zinc-700 dark:text-zinc-200">产物下载</p>
          <ul className="space-y-2">
            {artifacts.map((item) => (
              <li key={item.kind}>
                <a
                  href={item.downloadUrl}
                  className="text-sm font-medium text-violet-700 underline hover:text-violet-600 dark:text-violet-300"
                >
                  {item.label}
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}

      <a
        href={`/api/jobs/${encodeURIComponent(jobId)}/logs?limit=200`}
        target="_blank"
        rel="noreferrer"
        className="inline-block text-xs text-violet-700 underline dark:text-violet-300"
      >
        查看 JSONL 日志
      </a>
    </div>
  )
}
