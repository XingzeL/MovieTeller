import { useEffect, useState } from 'react'

export type WorkflowOverallProgress = {
  status: string
  percent: number
  label: string
  currentStage?: string | null
  lastError?: Record<string, unknown> | null
}

type Props = {
  outputRoot: string
  pollMs?: number
  active?: boolean
}

/** Polls GET /api/workflow/progress for a single overall progress bar. */
export function WorkflowProgressBar({
  outputRoot,
  pollMs = 2500,
  active = true,
}: Props) {
  const [progress, setProgress] = useState<WorkflowOverallProgress | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!active || !outputRoot.trim()) {
      return
    }

    let cancelled = false

    const fetchProgress = async () => {
      try {
        const params = new URLSearchParams({ outputRoot: outputRoot.trim() })
        const res = await fetch(`/api/workflow/progress?${params}`)
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
        if (!cancelled) {
          setError('无法读取工作流进度')
        }
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
  }, [active, outputRoot, pollMs])

  if (!active || !outputRoot.trim()) {
    return null
  }

  const percent = Math.max(0, Math.min(100, progress?.percent ?? 0))
  const label = progress?.label ?? '处理中'
  const done = progress?.status === 'succeeded' || progress?.status === 'failed'

  return (
    <div className="mt-4 rounded-lg border border-violet-200 bg-violet-50/80 px-4 py-3 dark:border-violet-900 dark:bg-violet-950/30">
      <div className="mb-2 flex items-center justify-between gap-2 text-sm">
        <span className="font-medium text-violet-900 dark:text-violet-100">{label}</span>
        <span className="tabular-nums text-violet-700 dark:text-violet-300">{percent}%</span>
      </div>
      <progress
        className="h-2 w-full overflow-hidden rounded-full accent-violet-600"
        value={percent}
        max={100}
      />
      {error && (
        <p className="mt-2 text-xs text-red-700 dark:text-red-300">{error}</p>
      )}
      {!done && !error && (
        <p className="mt-2 text-xs text-violet-700/80 dark:text-violet-300/80">
          整体进度（细分步骤请在终端查看）
        </p>
      )}
      {progress?.status === 'failed' && progress.lastError && (
        <p className="mt-2 text-xs text-red-800 dark:text-red-200">
          {(progress.lastError.error_message as string) || '任务失败'}
        </p>
      )}
    </div>
  )
}
