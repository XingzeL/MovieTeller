import { useCallback, useEffect, useState } from 'react'

import { apiFetch, ensureDevSession } from '../api/apiClient'
import { isClerkEnabled } from '../auth/clerkConfig'
import {
  ArtifactDownloadError,
  downloadRenderedVideo,
  downloadStudyCardsHtml,
} from '../api/downloadArtifact'
import { VideoStateBadge } from './VideoStateBadge'
import type { JobArtifactItem, JobDto } from '../types/job'
import { StudyCardPreviewFrame } from './StudyCardPreviewFrame'
import { WorkflowProgressBar } from './WorkflowProgressBar'

function JobSourceSummary({ job }: { job: JobDto }) {
  const source = job.originalSource
  if (!source) return null

  if (source.type === 'remote_url' && source.source_url) {
    let hostname = '远程视频'
    try {
      hostname = new URL(source.source_url).hostname.replace(/^www\./, '')
    } catch {
      /* keep fallback */
    }
    return (
      <div className="mt-2 rounded-lg border border-violet-200 bg-violet-50 px-3 py-2 text-xs dark:border-violet-900 dark:bg-violet-950/30">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-semibold text-violet-900 dark:text-violet-200">视频链接</span>
          <span className="text-violet-700 dark:text-violet-300">{hostname}</span>
        </div>
        <p className="mt-1 truncate text-violet-800/80 dark:text-violet-200/80" title={source.source_url}>
          {source.source_url}
        </p>
      </div>
    )
  }

  if (source.original_filename) {
    return (
      <p className="mt-2 text-xs text-zinc-500 dark:text-zinc-400">
        来源文件：{source.original_filename}
      </p>
    )
  }

  return null
}

type Props = {
  jobId: string
  onClear?: () => void
}

export function JobPanel({ jobId, onClear }: Props) {
  const [job, setJob] = useState<JobDto | null>(null)
  const [artifacts, setArtifacts] = useState<JobArtifactItem[]>([])
  const [error, setError] = useState<string | null>(null)
  const [videoDownloadError, setVideoDownloadError] = useState<string | null>(null)
  const [downloadingVideo, setDownloadingVideo] = useState(false)
  const [studyPreviewHtml, setStudyPreviewHtml] = useState<string | null>(null)

  const fetchJob = useCallback(async () => {
    const res = await apiFetch(`/api/jobs/${encodeURIComponent(jobId)}`)
    const data = (await res.json()) as { job?: JobDto; error?: string }
    if (!res.ok) {
      throw new Error(data.error ?? `Job request failed (${res.status})`)
    }
    return data.job ?? null
  }, [jobId])

  const fetchArtifacts = useCallback(async () => {
    const res = await apiFetch(`/api/jobs/${encodeURIComponent(jobId)}/artifacts`)
    const data = (await res.json()) as { artifacts?: JobArtifactItem[]; error?: string }
    if (!res.ok) return []
    return data.artifacts ?? []
  }, [jobId])

  useEffect(() => {
    void ensureDevSession()
  }, [])

  useEffect(() => {
    let cancelled = false
    const tick = async () => {
      try {
        const nextJob = await fetchJob()
        if (cancelled) return
        setJob(nextJob)
        setError(null)

        // Always fetch artifacts so we can show study cards / video as soon as they are ready
        // (study cards can appear before the full render succeeds)
        const items = await fetchArtifacts()
        if (!cancelled) setArtifacts(items)

        const study = items.find((a) => a.kind === 'studyCardsHtml')
        if (study) {
          const inlineRes = await apiFetch(
            `/api/jobs/${encodeURIComponent(jobId)}/artifacts/studyCardsHtml?inline=1`,
          )
          if (!cancelled && inlineRes.ok) {
            setStudyPreviewHtml(await inlineRes.text())
          }
        } else if (!cancelled) {
          setStudyPreviewHtml(null)
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

  const cancelInFlight =
    job?.status === 'canceling' || cancelRequested

  const handleCancel = async () => {
    await apiFetch(`/api/jobs/${encodeURIComponent(jobId)}/cancel`, { method: 'POST' })
    const nextJob = await fetchJob()
    setJob(nextJob)
  }

  const handleRetry = async () => {
    const res = await apiFetch(`/api/jobs/${encodeURIComponent(jobId)}/retry`, {
      method: 'POST',
    })
    const data = (await res.json()) as { error?: string }
    if (!res.ok) {
      setError(data.error ?? `重试失败 (${res.status})`)
      return
    }
    setError(null)
    const nextJob = await fetchJob()
    setJob(nextJob)
  }

  const canRetry = job?.status === 'failed' || job?.status === 'canceled'

  const downloadStudyCards = async () => {
    try {
      await downloadStudyCardsHtml(jobId)
    } catch {
      /* ignore — user can retry */
    }
  }

  const handleDownloadVideo = async () => {
    setDownloadingVideo(true)
    setVideoDownloadError(null)
    try {
      await downloadRenderedVideo(jobId)
      const nextJob = await fetchJob()
      setJob(nextJob)
    } catch (err) {
      if (err instanceof ArtifactDownloadError && err.status === 410) {
        setVideoDownloadError('视频已下载或已清理')
        const nextJob = await fetchJob()
        setJob(nextJob)
        return
      }
      setVideoDownloadError(err instanceof Error ? err.message : '下载失败')
    } finally {
      setDownloadingVideo(false)
    }
  }

  return (
    <div className="mt-6 space-y-4 rounded-xl border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-700 dark:bg-zinc-900/60">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-xs uppercase tracking-wide text-zinc-500">Job</p>
          <p className="font-mono text-sm text-zinc-800 dark:text-zinc-100">{jobId}</p>
        </div>
        <div className="flex gap-2">
          {!terminal && !cancelInFlight && (
            <button
              type="button"
              onClick={() => void handleCancel()}
              className="rounded-lg border border-zinc-300 px-3 py-1.5 text-xs font-medium text-zinc-700 hover:bg-white dark:border-zinc-600 dark:text-zinc-200"
            >
              取消
            </button>
          )}
          {canRetry && (
            <button
              type="button"
              onClick={() => void handleRetry()}
              className="rounded-lg border border-violet-300 px-3 py-1.5 text-xs font-medium text-violet-800 hover:bg-violet-50 dark:border-violet-600 dark:text-violet-200"
            >
              重试
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

      {job ? <JobSourceSummary job={job} /> : null}

      {job && (
        <p className="flex flex-wrap items-center gap-2 text-sm text-zinc-600 dark:text-zinc-300">
          <span>
            状态：
            <span className="font-medium">
              {job.status === 'canceling' ? '取消中' : job.status}
            </span>
            {cancelRequested && job.status !== 'canceled' && job.status !== 'canceling'
              ? ' · 取消已请求'
              : null}
            {job.currentStage ? ` · 阶段 ${job.currentStage}` : null}
          </span>
          {job.videoState ? <VideoStateBadge state={job.videoState} /> : null}
        </p>
      )}

      <WorkflowProgressBar jobId={jobId} active={!terminal} />

      {/* Progressive beautiful previews — study cards appear first, then video */}
      {(() => {
        const study = artifacts.find((a) => a.kind === 'studyCardsHtml')
        const video = job?.canDownloadVideo
          ? artifacts.find((a) => a.kind === 'renderedVideo')
          : undefined

        if (!study && !video) return null

        return (
          <div className="space-y-6 pt-2">
            {/* Study Cards Preview (first ~10% / top of the beautiful template) */}
            {study && (
              <div className="overflow-hidden rounded-2xl border border-[#d1fae5] bg-white shadow-sm">
                <div className="flex items-center justify-between border-b border-[#d1fae5] bg-[#f0fdf4] px-5 py-3">
                  <div>
                    <div className="text-sm font-semibold text-[#166534]">学习卡已就绪</div>
                    <div className="text-xs text-[#4b5563]">预览 · 开头精彩部分（完整版可下载）</div>
                  </div>
                  <button
                    type="button"
                    onClick={() => void downloadStudyCards()}
                    className="inline-flex items-center gap-2 rounded-xl bg-[#166534] px-4 py-2 text-sm font-semibold text-white shadow transition hover:bg-[#14532d]"
                  >
                    下载完整学习卡
                  </button>
                </div>
                <div className="p-3">
                  <StudyCardPreviewFrame
                    htmlContent={studyPreviewHtml}
                    src={
                      isClerkEnabled()
                        ? undefined
                        : `${study.downloadUrl}?inline=true`
                    }
                    title="学习卡预览"
                  />
                </div>
                <div className="border-t border-[#d1fae5] bg-[#f8fafc] px-5 py-2.5 text-center text-xs text-[#64748b]">
                  仅展示学习卡开头预览 · 完整内容请下载 HTML 离线浏览
                </div>
              </div>
            )}

            {video && (
              <div className="overflow-hidden rounded-2xl border border-[#d1fae5] bg-white shadow-sm">
                <div className="flex items-center justify-between border-b border-[#d1fae5] bg-[#f0fdf4] px-5 py-3">
                  <div>
                    <div className="text-sm font-semibold text-[#166534]">解说视频已生成</div>
                    <div className="text-xs text-[#4b5563]">完整视频仅可成功下载一次</div>
                  </div>
                  <button
                    type="button"
                    disabled={downloadingVideo}
                    onClick={() => void handleDownloadVideo()}
                    className="inline-flex items-center gap-2 rounded-xl bg-[#166534] px-4 py-2 text-sm font-semibold text-white shadow transition hover:bg-[#14532d] disabled:opacity-60"
                  >
                    {downloadingVideo ? '下载中…' : '下载完整视频'}
                  </button>
                </div>
                <div className="bg-white px-5 py-4 text-sm text-[#4b5563]">
                  下载成功后，系统会标记视频已下载并清理视频文件；学习卡会继续保留。
                  {videoDownloadError ? (
                    <p className="mt-2 text-amber-700">{videoDownloadError}</p>
                  ) : null}
                </div>
              </div>
            )}
          </div>
        )
      })()}

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

      {/* 旧的通用产物列表已由上方的精美预览区块替代（更突出「下载完整学习卡 / 完整视频」） */}

    </div>
  )
}
