import { useEffect, useState } from 'react'

import { apiFetch } from '../api/apiClient'

export type WorkflowOverallProgress = {
  status: string
  percent: number
  label: string
  currentStage?: string | null
  lastError?: Record<string, unknown> | null
}

type Props = {
  jobId: string
  pollMs?: number
  active?: boolean
  /** Compact mode for embedding in history cards / lists. Much smaller footprint. */
  compact?: boolean
}

/** Polls Job workflow progress. */
export function WorkflowProgressBar({ jobId, pollMs = 2500, active = true, compact = false }: Props) {
  const [progress, setProgress] = useState<WorkflowOverallProgress | null>(null)
  const [error, setError] = useState<string | null>(null)

  const trimmedJobId = jobId.trim()
  const enabled = active && trimmedJobId.length > 0

  useEffect(() => {
    if (!enabled) return

    let cancelled = false

    const fetchProgress = async () => {
      try {
        const res = await apiFetch(`/api/jobs/${encodeURIComponent(trimmedJobId)}/progress`)
        const data = (await res.json()) as {
          progress?: WorkflowOverallProgress
          error?: string
        }
        if (cancelled) return
        if (!res.ok) {
          setError(data.error ?? `Progress request failed (${res.status})`)
          return
        }
        setError(null)
        if (data.progress) setProgress(data.progress)
      } catch {
        if (!cancelled) setError('无法读取工作流进度')
      }
    }

    void fetchProgress()
    const id = window.setInterval(() => {
      void fetchProgress()
    }, pollMs)

    return () => {
      cancelled = true
      window.clearInterval(id)
    }
  }, [enabled, trimmedJobId, pollMs])

  if (!enabled) return null

  const percent = Math.max(0, Math.min(100, progress?.percent ?? 0))
  const label = progress?.label ?? '处理中'
  const done =
    progress?.status === 'succeeded' ||
    progress?.status === 'failed' ||
    progress?.status === 'canceled'

  // Full (thick) progress bar for detail page
  const fullBar = (
    <div className="relative h-4 w-full overflow-hidden rounded-full bg-[#e5f5e9]">
      <div
        className="absolute left-0 top-0 h-4 rounded-full bg-gradient-to-r from-[#4ade80] via-[#86efac] to-[#4ade80] transition-all duration-500 ease-out"
        style={{ width: `${percent}%` }}
      />
      {!done && (
        <div
          className="absolute top-0 h-4 w-1/3 animate-[shimmer_1.8s_infinite] bg-gradient-to-r from-transparent via-white/60 to-transparent"
          style={{ left: `${Math.min(95, percent)}%` }}
        />
      )}
    </div>
  )

  // Compact thin bar for dashboard history cards
  const compactBar = (
    <div className="relative h-1.5 w-full overflow-hidden rounded-full bg-[#e5f5e9]">
      <div
        className="absolute left-0 top-0 h-1.5 rounded-full bg-gradient-to-r from-[#4ade80] via-[#86efac] to-[#4ade80] transition-all duration-500 ease-out"
        style={{ width: `${percent}%` }}
      />
      {!done && (
        <div
          className="absolute top-0 h-1.5 w-1/3 animate-[shimmer_1.8s_infinite] bg-gradient-to-r from-transparent via-white/60 to-transparent"
          style={{ left: `${Math.min(95, percent)}%` }}
        />
      )}
    </div>
  )

  if (compact) {
    return (
      <div className="mt-2">
        <div className="mb-1 flex items-center justify-between gap-2 text-[11px] leading-none">
          <span className="font-medium text-[#166534] truncate" title={label}>
            {label}
          </span>
          <span className="tabular-nums font-mono text-[#166534] flex-shrink-0">{percent}%</span>
        </div>
        {compactBar}
        {error && <p className="mt-1 text-[10px] text-red-600">{error}</p>}
        {progress?.status === 'failed' && progress.lastError && (
          <p className="mt-1 text-[10px] text-red-600">
            {(progress.lastError.error_message as string) || '任务失败'}
          </p>
        )}
      </div>
    )
  }

  // Full mode (original detail page usage)
  return (
    <div className="mt-4 rounded-2xl border border-[#d1fae5] bg-white/70 px-5 py-4 shadow-sm backdrop-blur">
      <div className="mb-3 flex items-center justify-between text-sm">
        <span className="font-semibold tracking-tight text-[#166534]">{label}</span>
        <span className="tabular-nums font-mono text-base font-medium text-[#166534]">{percent}%</span>
      </div>

      {fullBar}

      {error && <p className="mt-3 text-xs text-red-600">{error}</p>}

      {!done && !error && (
        <p className="mt-2.5 text-xs text-[#4b5563]">
          正在为你生成专属解说声道与学习卡片 · 请稍候
        </p>
      )}

      {progress?.status === 'failed' && progress.lastError && (
        <p className="mt-3 text-xs text-red-600">
          {(progress.lastError.error_message as string) || '任务失败'}
        </p>
      )}
    </div>
  )
}
