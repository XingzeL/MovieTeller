import { useEffect, useMemo, useState } from 'react'

import type { JobListItem, JobListResponse, JobStatus } from '../types/job'

type DashboardProps = {
  onGoHome: () => void
  onCreateVideo: () => void
  onSelectJob: (jobId: string) => void
}

const HISTORY_LIMIT = 8

function statusLabel(status: JobStatus) {
  switch (status) {
    case 'succeeded':
      return '已完成'
    case 'running':
      return '生成中'
    case 'queued':
      return '排队中'
    case 'failed':
      return '失败'
    case 'canceled':
      return '已取消'
  }
}

function StatusBadge({ status }: { status: JobStatus }) {
  if (status === 'succeeded') {
    return (
      <span className="inline-flex rounded-full bg-[#d1fae5] px-2.5 py-1 text-xs font-medium text-[#166534]">
        {statusLabel(status)}
      </span>
    )
  }

  if (status === 'running' || status === 'queued') {
    return (
      <span className="inline-flex rounded-full bg-amber-100 px-2.5 py-1 text-xs font-medium text-amber-700">
        {statusLabel(status)}
      </span>
    )
  }

  return (
    <span className="inline-flex rounded-full bg-red-100 px-2.5 py-1 text-xs font-medium text-red-600">
      {statusLabel(status)}
    </span>
  )
}

function formatDate(value?: string) {
  if (!value) return '未知时间'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function displayTitle(job: JobListItem) {
  return (
    job.originalSource?.original_filename ||
    job.inputFileName ||
    job.originalSource?.source_url ||
    job.jobId
  )
}

function SourceInfo({ job }: { job: JobListItem }) {
  const source = job.originalSource
  if (!source) return null

  if (source.type === 'remote_url' && source.source_url) {
    return (
      <div className="truncate text-[11px] text-[#718096]" title={source.source_url}>
        来源：远程链接
      </div>
    )
  }

  if (source.original_filename) {
    return (
      <div className="truncate text-[11px] text-[#718096]" title={source.original_filename}>
        来源：{source.original_filename}
      </div>
    )
  }

  return null
}

export function Dashboard({ onGoHome, onCreateVideo, onSelectJob }: DashboardProps) {
  const [jobs, setJobs] = useState<JobListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [hiddenThumbnails, setHiddenThumbnails] = useState<Record<string, true>>({})

  useEffect(() => {
    const fetchJobs = async () => {
      try {
        const res = await fetch(`/api/jobs?limit=${HISTORY_LIMIT}`)
        const data = (await res.json()) as JobListResponse & { error?: string }
        if (!res.ok) {
          throw new Error(data.error ?? `无法加载历史记录 (${res.status})`)
        }
        setJobs(data.jobs)
        setError(null)
      } catch (err) {
        setError(err instanceof Error ? err.message : '无法加载历史记录')
      } finally {
        setLoading(false)
      }
    }

    void fetchJobs()
  }, [])

  const filteredJobs = useMemo(() => {
    const keyword = query.trim().toLowerCase()
    if (!keyword) return jobs
    return jobs.filter((job) => displayTitle(job).toLowerCase().includes(keyword))
  }, [jobs, query])

  const handleReGenerate = (job: JobListItem) => {
    console.log('Re-generating from job:', job)
    onCreateVideo()
  }

  return (
    <div className="flex min-h-dvh bg-[#f0fdf4] text-[#4a5568]">
      <div className="w-56 flex-shrink-0 border-r border-[#d1fae5] bg-white">
        <div className="p-5">
          <div onClick={onGoHome} className="mb-8 flex cursor-pointer items-center gap-2">
            <div className="bg-gradient-to-r from-[#86efac] to-[#4ade80] bg-clip-text text-2xl font-extrabold tracking-tighter text-transparent">
              NarraLingo
            </div>
            <span className="rounded bg-[#d1fae5] px-1.5 py-0.5 text-[10px] font-medium text-[#166534]">
              Beta
            </span>
          </div>

          <nav className="space-y-1 text-sm">
            <button
              onClick={onGoHome}
              className="flex w-full items-center gap-3 rounded-xl bg-[#f0fdf4] px-3 py-2.5 text-left font-medium text-[#166534]"
            >
              <span className="text-lg">Home</span>
            </button>

            <button className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left font-medium text-[#4b5563] transition hover:bg-[#f0fdf4]">
              <span>Buy Credits</span>
            </button>

            <div className="pt-2">
              <div className="mb-1 px-3 text-[10px] font-semibold tracking-widest text-[#86efac]">
                TOOLS
              </div>
              <button className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left font-medium text-[#4b5563] transition hover:bg-[#f0fdf4]">
                <span>Usage &amp; History</span>
              </button>
              <button className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left font-medium text-[#4b5563] transition hover:bg-[#f0fdf4]">
                <span>Contact Support</span>
              </button>
            </div>
          </nav>
        </div>

        <div className="absolute bottom-0 left-0 w-56 border-t border-[#d1fae5] bg-white p-4">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-[#86efac] to-[#4ade80] text-sm font-semibold text-white">
              U
            </div>
            <div className="text-sm">
              <div className="font-medium text-[#166534]">User Demo</div>
              <div className="text-xs text-[#718096]">Free Plan</div>
            </div>
          </div>
        </div>
      </div>

      <div className="flex flex-1 flex-col">
        <div className="flex items-center justify-between border-b border-[#d1fae5] bg-white px-8 py-4">
          <div>
            <div className="text-xl font-semibold tracking-tight text-[#166534]">
              Your Learning Videos
            </div>
            <div className="text-sm text-[#718096]">
              Create and manage your AI-powered language learning content
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button className="rounded-full border border-[#d1fae5] bg-white px-5 py-2 text-sm font-semibold text-[#166534] transition hover:bg-[#f0fdf4]">
              Quick Start
            </button>
            <button
              onClick={onCreateVideo}
              className="flex items-center gap-2 rounded-full bg-[#166534] px-5 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-[#14532d]"
            >
              Create a Video
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-auto p-8">
          <div className="mb-6 flex items-center justify-between">
            <div>
              <div className="text-lg font-semibold text-[#166534]">Recent Creations</div>
              <div className="text-sm text-[#718096]">{filteredJobs.length} videos</div>
            </div>
            <input
              type="text"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search videos..."
              className="w-64 rounded-xl border border-[#d1fae5] bg-white px-4 py-2 text-sm placeholder:text-[#9ca3af] focus:outline-none focus:ring-1 focus:ring-[#86efac]"
            />
          </div>

          <div className="mb-4 text-[12px] text-[#64748b]">
            为控制存储成本，生成的视频文件在您下载一次后会自动清理。学习卡将长期保留。
          </div>

          {error && (
            <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {loading ? (
            <div className="py-12 text-center text-[#718096]">加载中...</div>
          ) : filteredJobs.length === 0 ? (
            <div className="py-12 text-center">
              <div className="mb-2 text-xl font-semibold text-[#166534]">还没有创建过视频</div>
              <button onClick={onCreateVideo} className="mt-4 text-[#166534] underline">
                立即创建第一个视频
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {filteredJobs.map((job) => {
                const isSucceeded = job.status === 'succeeded'
                const isActive = job.status === 'running' || job.status === 'queued'
                const videoUnavailable = Boolean(job.videoDownloadedAt || job.videoPurgedAt)
                const thumbnailUrl = `/api/jobs/${encodeURIComponent(job.jobId)}/thumbnail`
                const showThumbnail = !hiddenThumbnails[job.jobId]

                return (
                  <article
                    key={job.jobId}
                    className="group overflow-hidden rounded-2xl border border-[#d1fae5] bg-white shadow-sm transition hover:shadow-md"
                  >
                    <button
                      type="button"
                      onClick={() => onSelectJob(job.jobId)}
                      className="relative flex aspect-video w-full items-center justify-center overflow-hidden bg-gradient-to-br from-[#86efac]/30 to-[#4ade80]/30 text-left"
                    >
                      {showThumbnail ? (
                        <img
                          src={thumbnailUrl}
                          alt=""
                          loading="lazy"
                          onError={() =>
                            setHiddenThumbnails((prev) => ({ ...prev, [job.jobId]: true }))
                          }
                          className="h-full w-full object-cover transition duration-300 group-hover:scale-[1.03]"
                        />
                      ) : (
                        <div className="text-sm font-semibold text-[#166534] opacity-70">
                          查看任务详情
                        </div>
                      )}
                      <div className="absolute inset-0 bg-[#052e16]/0 transition group-hover:bg-[#052e16]/10" />
                    </button>

                    <div className="p-4">
                      <button
                        type="button"
                        onClick={() => onSelectJob(job.jobId)}
                        className="line-clamp-2 w-full text-left font-semibold text-[#166534] hover:underline"
                        title={displayTitle(job)}
                      >
                        {displayTitle(job)}
                      </button>

                      <div className="mt-1 text-xs text-[#718096]">{formatDate(job.createdAt)}</div>
                      <SourceInfo job={job} />

                      <div className="mt-3 flex items-center justify-between gap-3">
                        <StatusBadge status={job.status} />
                        <button
                          type="button"
                          onClick={() => onSelectJob(job.jobId)}
                          className="text-xs font-semibold text-[#166534] hover:underline"
                        >
                          详情
                        </button>
                      </div>

                      <div className="mt-4 flex flex-wrap gap-2">
                        {isSucceeded && !videoUnavailable && (
                          <a
                            href={`/api/jobs/${encodeURIComponent(job.jobId)}/artifacts/renderedVideo`}
                            download
                            className="rounded-lg bg-[#166534] px-3 py-1.5 text-xs font-semibold text-white no-underline transition hover:bg-[#14532d] active:scale-[0.985]"
                          >
                            下载完整视频
                          </a>
                        )}

                        {isSucceeded && videoUnavailable && (
                          <button
                            type="button"
                            onClick={() => handleReGenerate(job)}
                            className="rounded-lg bg-[#166534] px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-[#14532d] active:scale-[0.985]"
                          >
                            重新生成解说
                          </button>
                        )}

                        {isSucceeded && (
                          <a
                            href={`/api/jobs/${encodeURIComponent(job.jobId)}/artifacts/studyCardsHtml`}
                            download
                            className="rounded-lg border border-[#86efac] bg-white px-3 py-1.5 text-xs font-semibold text-[#166534] no-underline transition hover:bg-[#f0fdf4] active:scale-[0.985]"
                          >
                            下载学习卡
                          </a>
                        )}

                        {(job.status === 'failed' || job.status === 'canceled') && (
                          <button
                            type="button"
                            onClick={() => handleReGenerate(job)}
                            className="rounded-lg bg-red-600 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-red-700 active:scale-[0.985]"
                          >
                            重新生成
                          </button>
                        )}

                        {isActive && (
                          <span className="rounded-lg bg-amber-100 px-3 py-1.5 text-xs font-medium text-amber-700">
                            {statusLabel(job.status)}
                          </span>
                        )}
                      </div>

                      {isSucceeded && videoUnavailable && (
                        <div className="mt-2 text-[10px] leading-snug text-[#9ca3af]">
                          视频文件已清理或等待清理。学习卡仍可下载。
                        </div>
                      )}
                    </div>
                  </article>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
