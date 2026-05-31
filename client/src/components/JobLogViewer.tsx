import { useCallback, useEffect, useRef, useState } from 'react'

import { apiFetch } from '../api/apiClient'
import type { JobLogsResponse } from '../types/job'

const MAX_VISIBLE_LINES = 200
const POLL_MS_ACTIVE = 2000
const PAGE_LIMIT = 80

type Props = {
  jobId: string
  active?: boolean
}

function formatLogLine(line: Record<string, unknown>): string {
  if (typeof line.raw === 'string') {
    return line.raw
  }
  const event = line.event
  if (typeof event === 'string') {
    const parts = [event]
    if (line.stage != null) parts.push(`stage=${String(line.stage)}`)
    if (line.segment_index != null) parts.push(`seg=${String(line.segment_index)}`)
    if (line.group_index != null) parts.push(`grp=${String(line.group_index)}`)
    const msg = line.message ?? line.error_message ?? line.detail
    if (msg != null) parts.push(String(msg))
    return parts.join(' · ')
  }
  try {
    return JSON.stringify(line)
  } catch {
    return String(line)
  }
}

export function JobLogViewer({ jobId, active = true }: Props) {
  const [lines, setLines] = useState<string[]>([])
  const [logError, setLogError] = useState<string | null>(null)
  const [expanded, setExpanded] = useState(true)
  const afterRef = useRef(0)
  const scrollRef = useRef<HTMLPreElement>(null)
  const stickBottomRef = useRef(true)

  const appendLines = useCallback((formatted: string[]) => {
    if (formatted.length === 0) return
    setLines((prev) => {
      const next = [...prev, ...formatted]
      return next.length > MAX_VISIBLE_LINES
        ? next.slice(-MAX_VISIBLE_LINES)
        : next
    })
  }, [])

  const fetchLogs = useCallback(async () => {
    const after = afterRef.current
    const url = `/api/jobs/${encodeURIComponent(jobId)}/logs?limit=${PAGE_LIMIT}&after=${after}`
    const res = await apiFetch(url)
    const data = (await res.json()) as JobLogsResponse & { error?: string }
    if (!res.ok) {
      throw new Error(data.error ?? `Logs request failed (${res.status})`)
    }
    const batch = (data.lines ?? []).map((line) =>
      formatLogLine(line as Record<string, unknown>)
    )
    if (typeof data.nextOffset === 'number' && data.nextOffset >= after) {
      afterRef.current = data.nextOffset
    }
    appendLines(batch)
  }, [appendLines, jobId])

  useEffect(() => {
    afterRef.current = 0
    stickBottomRef.current = true
    setLines([])
    setLogError(null)
  }, [jobId])

  useEffect(() => {
    if (!active) {
      void fetchLogs().catch((err) => {
        setLogError(err instanceof Error ? err.message : '无法读取日志')
      })
      return
    }

    let cancelled = false
    const tick = async () => {
      try {
        await fetchLogs()
        if (!cancelled) setLogError(null)
      } catch (err) {
        if (!cancelled) {
          setLogError(err instanceof Error ? err.message : '无法读取日志')
        }
      }
    }

    void tick()
    const id = window.setInterval(() => void tick(), POLL_MS_ACTIVE)
    return () => {
      cancelled = true
      window.clearInterval(id)
    }
  }, [active, fetchLogs, jobId])

  useEffect(() => {
    if (!stickBottomRef.current || !scrollRef.current) return
    scrollRef.current.scrollTop = scrollRef.current.scrollHeight
  }, [lines])

  const handleScroll = () => {
    const el = scrollRef.current
    if (!el) return
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 48
    stickBottomRef.current = nearBottom
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="text-sm font-medium text-zinc-700 dark:text-zinc-200"
        >
          {expanded ? '▼' : '▶'} 运行日志
          {lines.length > 0 ? ` (${lines.length})` : ''}
        </button>
        <a
          href={`/api/jobs/${encodeURIComponent(jobId)}/logs?limit=200`}
          target="_blank"
          rel="noreferrer"
          className="text-xs text-violet-700 underline dark:text-violet-300"
        >
          原始 JSONL
        </a>
      </div>

      {expanded && (
        <>
          {logError && (
            <p className="text-xs text-red-700 dark:text-red-300">{logError}</p>
          )}
          <pre
            ref={scrollRef}
            onScroll={handleScroll}
            className="max-h-56 overflow-auto rounded-lg border border-zinc-200 bg-zinc-950 px-3 py-2 font-mono text-[11px] leading-relaxed text-zinc-100 dark:border-zinc-700"
          >
            {lines.length === 0 ? (
              <span className="text-zinc-500">等待日志输出…</span>
            ) : (
              lines.map((line, index) => <div key={index}>{line}</div>)
            )}
          </pre>
        </>
      )}
    </div>
  )
}
