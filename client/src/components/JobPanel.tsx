import { useCallback, useEffect, useState } from 'react'

import { apiFetch } from '../api/apiClient'
import type { JobArtifactItem, JobDto } from '../types/job'
import { StudyCardPreviewFrame } from './StudyCardPreviewFrame'
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
                  <a
                    href={study.downloadUrl}
                    download
                    className="inline-flex items-center gap-2 rounded-xl bg-[#166534] px-4 py-2 text-sm font-semibold text-white shadow transition hover:bg-[#14532d]"
                  >
                    下载完整学习卡
                  </a>
                </div>
                <div className="p-3">
                  <StudyCardPreviewFrame
                    src={`${study.downloadUrl}?inline=true`}
                    title="学习卡预览"
                  />
                </div>
                <div className="border-t border-[#d1fae5] bg-[#f8fafc] px-5 py-2.5 text-center text-xs text-[#64748b]">
                  仅展示学习卡开头预览 · 完整内容请下载 HTML 离线浏览
                </div>
              </div>
            )}

            {/* Video Preview (first 10 seconds feel) */}
            {video && (
              <div className="overflow-hidden rounded-2xl border border-[#d1fae5] bg-white shadow-sm">
                <div className="flex items-center justify-between border-b border-[#d1fae5] bg-[#f0fdf4] px-5 py-3">
                  <div>
                    <div className="text-sm font-semibold text-[#166534]">解说视频已生成</div>
                    <div className="text-xs text-[#4b5563]">预览 · 前 10 秒（完整视频可下载）</div>
                  </div>
                  <a
                    href={video.downloadUrl}
                    download
                    className="inline-flex items-center gap-2 rounded-xl bg-[#166534] px-4 py-2 text-sm font-semibold text-white shadow transition hover:bg-[#14532d]"
                  >
                    下载完整视频
                  </a>
                </div>
                <div className="p-4">
                  <video
                    controls
                    className="mx-auto w-full max-w-[720px] rounded-xl border border-[#d1fae5] bg-black"
                    style={{ maxHeight: '320px' }}
                    src={`${video.downloadUrl}?inline=true`}
                  >
                    您的浏览器不支持 video 标签。
                  </video>
                  <p className="mt-2 text-center text-xs text-[#64748b]">
                    视频从开头播放 · 拖动进度条可查看更多内容
                  </p>
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
