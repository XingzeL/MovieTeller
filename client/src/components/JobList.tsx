import { useCallback, useEffect, useState } from 'react'

import type { JobListItem, JobListResponse } from '../types/job'

const TERMINAL = new Set(['succeeded', 'failed', 'canceled'])

const STATUS_LABEL: Record<string, string> = {
  queued: '排队中',
  running: '运行中',
  succeeded: '成功',
  failed: '失败',
  canceled: '已取消',
}

type Props = {
  selectedJobId?: string | null
  onSelectJob: (jobId: string) => void
  pollMs?: number
}

function formatTime(iso?: string): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString()
}

export function JobList({ selectedJobId, onSelectJob, pollMs = 5000 }: Props) {
  const [jobs, setJobs] = useState<JobListItem[]>([])
  const [total, setTotal] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const fetchList = useCallback(async () => {
    const res = await fetch('/api/jobs?limit=30&offset=0')
    const data = (await res.json()) as JobListResponse & { error?: string }
    if (!res.ok) {
      throw new Error(data.error ?? `列表请求失败 (${res.status})`)
    }
    setJobs(data.jobs ?? [])
    setTotal(data.total ?? 0)
  }, [])

  useEffect(() => {
    let cancelled = false

    const tick = async () => {
      try {
        await fetchList()
        if (!cancelled) {
          setError(null)
          setLoading(false)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : '无法加载任务列表')
          setLoading(false)
        }
      }
    }

    void tick()
    const id = window.setInterval(() => {
      void tick()
    }, pollMs)

    return () => {
      cancelled = true
      window.clearInterval(id)
    }
  }, [fetchList, pollMs])

  const hasActive = jobs.some((j) => !TERMINAL.has(j.status))

  return (
    <section className="mb-8 rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-sm font-semibold text-zinc-800 dark:text-zinc-100">最近任务</h2>
        <span className="text-xs text-zinc-500">
          {total} 个{hasActive ? ' · 自动刷新' : ''}
        </span>
      </div>

      {loading && jobs.length === 0 && (
        <p className="text-sm text-zinc-500">加载中…</p>
      )}

      {error && (
        <p className="text-sm text-red-700 dark:text-red-300">{error}</p>
      )}

      {!loading && !error && jobs.length === 0 && (
        <p className="text-sm text-zinc-500">暂无任务，上传视频即可创建第一个 Job。</p>
      )}

      {jobs.length > 0 && (
        <ul className="divide-y divide-zinc-100 dark:divide-zinc-800">
          {jobs.map((job) => {
            const selected = selectedJobId === job.jobId
            const cancelPending =
              Boolean(job.cancelRequestedAt) && job.status !== 'canceled'
            return (
              <li key={job.jobId}>
                <button
                  type="button"
                  onClick={() => onSelectJob(job.jobId)}
                  className={`flex w-full flex-col gap-1 px-2 py-3 text-left transition rounded-lg ${
                    selected
                      ? 'bg-violet-50 dark:bg-violet-950/40'
                      : 'hover:bg-zinc-50 dark:hover:bg-zinc-800/60'
                  }`}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-mono text-xs text-zinc-700 dark:text-zinc-200">
                      {job.jobId.slice(0, 8)}…
                    </span>
                    <span className="text-xs font-medium text-zinc-600 dark:text-zinc-300">
                      {STATUS_LABEL[job.status] ?? job.status}
                      {cancelPending ? ' · 取消中' : ''}
                    </span>
                  </div>
                  {job.inputFileName && (
                    <span className="truncate text-sm text-zinc-800 dark:text-zinc-100">
                      {job.inputFileName}
                    </span>
                  )}
                  <span className="text-xs text-zinc-500">
                    更新 {formatTime(job.updatedAt)}
                    {job.currentStage ? ` · ${job.currentStage}` : ''}
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
