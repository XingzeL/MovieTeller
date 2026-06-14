import { Component } from 'react'

import { apiFetch, ensureDevSession } from './api/apiClient'
import { JobPanel } from './components/JobPanel'
import { UploadForm } from './components/UploadForm'
import type { VideoSourceMode } from './modules/videoUpload'
import { validateVideoUrl } from './modules/videoUpload'
import type { CreateJobResponse, QuotaClipReason } from './types/job'
import { buildQuotaClipNotice } from './utils/quotaClipMessages'
import { formatVideoDownloadError } from './utils/videoDownloadErrors'

type UploadPageProps = {
  jobId?: string | null
  onJobIdChange?: (jobId: string) => void
  onClearJob?: () => void
}

const VIDEO_LANGUAGES = [
  { value: 'auto', label: '自动检测' },
  { value: 'en', label: '英语' },
  { value: 'zh', label: '中文' },
  { value: 'ja', label: '日语' },
  { value: 'ko', label: '韩语' },
  { value: 'vi', label: '越南语' },
  { value: 'fr', label: '法语' },
  { value: 'de', label: '德语' },
  { value: 'es', label: '西班牙语' },
]

const TTS_LANGUAGES = [
  { value: 'en', label: '英语' },
  { value: 'zh', label: '中文' },
  { value: 'ja', label: '日语' },
  { value: 'ko', label: '韩语' },
  { value: 'vi', label: '越南语' },
  { value: 'fr', label: '法语' },
  { value: 'de', label: '德语' },
  { value: 'es', label: '西班牙语' },
]

function uploadErrorMessage(input: {
  code?: string
  reason?: string
  error?: string
  status: number
}) {
  if (input.code === 'plan_quota_exhausted') {
    if (input.reason === 'narration_quota_exhausted') {
      return '解说额度不足。请关闭“生成解说声道”后重试，或购买解说包后再生成。'
    }
    if (input.reason === 'daily_processing_quota_exhausted') {
      return '今日基础视频处理额度已用完。请明天再试，或升级套餐。'
    }
    return '基础视频处理额度不足，当前无法继续处理视频。请购买或升级套餐，也可以等下个计费周期额度恢复。'
  }
  if (input.code === 'video_probe_failed') {
    return '无法读取视频时长。请确认视频文件可正常播放后再上传。'
  }
  if (input.code === 'video_download_failed') {
    const hint = formatVideoDownloadError(input.error)
    return `无法从该链接下载视频。${hint}`
  }
  return input.error ?? `Request failed (${input.status})`
}

type ClipNotice = {
  sourceDurationSec: number
  processedDurationSec: number
  reasons: QuotaClipReason[]
}

type UploadPageState = {
  sourceMode: VideoSourceMode
  file: File | null
  videoUrl: string
  jobId: string | null
  enableSpeech: boolean
  cefrLevel: string
  videoLanguage: string
  ttsLanguage: string
  loading: boolean
  error: string | null
  clipNotice: ClipNotice | null
}

/** 上传视频并创建后台 Job；jobId 由 App 通过 URL 与列表同步。 */
export default class UploadPage extends Component<UploadPageProps, UploadPageState> {
  state: UploadPageState = {
    sourceMode: 'file',
    file: null,
    videoUrl: '',
    jobId: this.props.jobId ?? null,
    enableSpeech: true,
    cefrLevel: 'B1',
    videoLanguage: 'auto',
    ttsLanguage: 'en',
    loading: false,
    error: null,
    clipNotice: null,
  }

  componentDidUpdate(prevProps: UploadPageProps) {
    const next = this.props.jobId ?? null
    const prev = prevProps.jobId ?? null
    if (next !== prev && next !== this.state.jobId) {
      this.setState({ jobId: next })
    }
  }

  private get submitEnabled(): boolean {
    if (this.state.loading) return false
    if (this.state.sourceMode === 'file') {
      return this.state.file !== null
    }
    return validateVideoUrl(this.state.videoUrl) === null
  }

  private buildJobOptions() {
    return {
      enablePolish: true,
      enableSpeech: this.state.enableSpeech,
      enableSubtitleContext: true,
      enableEmbedVideo: true,
      cefrLevel: this.state.cefrLevel,
      sourceLanguage: this.state.videoLanguage,
      ttsLanguage: this.state.ttsLanguage,
      narrationLanguage: this.state.ttsLanguage,
      subtitleLanguage: this.state.videoLanguage,
    }
  }

  private handleCreateJob = async () => {
    const { sourceMode, file, videoUrl, loading } = this.state
    if (loading || !this.submitEnabled) return
    this.setState({ error: null, clipNotice: null, loading: true })
    try {
      await ensureDevSession()
      const options = this.buildJobOptions()
      let res: Response
      if (sourceMode === 'file') {
        if (!file) {
          this.setState({ loading: false })
          return
        }
        const fd = new FormData()
        fd.append('file', file)
        fd.append('enablePolish', options.enablePolish ? 'true' : 'false')
        fd.append('enableSpeech', options.enableSpeech ? 'true' : 'false')
        fd.append('enableSubtitleContext', options.enableSubtitleContext ? 'true' : 'false')
        fd.append('enableEmbedVideo', options.enableEmbedVideo ? 'true' : 'false')
        fd.append('cefrLevel', options.cefrLevel)
        fd.append('sourceLanguage', options.sourceLanguage)
        fd.append('ttsLanguage', options.ttsLanguage)
        fd.append('narrationLanguage', options.narrationLanguage)
        fd.append('subtitleLanguage', options.subtitleLanguage)
        res = await apiFetch('/api/jobs', { method: 'POST', body: fd })
      } else {
        const urlErr = validateVideoUrl(videoUrl)
        if (urlErr) {
          this.setState({ error: urlErr, loading: false })
          return
        }
        res = await apiFetch('/api/jobs', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            sourceUrl: videoUrl.trim(),
            enablePolish: options.enablePolish,
            enableSpeech: options.enableSpeech,
            enableSubtitleContext: options.enableSubtitleContext,
            enableEmbedVideo: options.enableEmbedVideo,
            cefrLevel: options.cefrLevel,
            sourceLanguage: options.sourceLanguage,
            ttsLanguage: options.ttsLanguage,
            narrationLanguage: options.narrationLanguage,
            subtitleLanguage: options.subtitleLanguage,
          }),
        })
      }
      const data = (await res.json()) as CreateJobResponse & {
        error?: string
        code?: string
        reason?: string
      }
      if (!res.ok) {
        this.setState({
          error: uploadErrorMessage({
            code: data.code,
            reason: data.reason,
            error: data.error,
            status: res.status,
          }),
          loading: false,
        })
        return
      }
      const nextJobId = data.jobId
      this.props.onJobIdChange?.(nextJobId)
      const clipNotice =
        data.quotaClipApplied &&
        data.sourceDurationSec != null &&
        data.processedDurationSec != null &&
        data.sourceDurationSec > data.processedDurationSec
          ? {
              sourceDurationSec: data.sourceDurationSec,
              processedDurationSec: data.processedDurationSec,
              reasons: data.quotaClipReasons ?? [],
            }
          : null
      this.setState({ jobId: nextJobId, loading: false, clipNotice })
    } catch {
      this.setState({
        error: 'Network error. Is the server running on port 3001?',
        loading: false,
      })
    }
  }

  render() {
    const {
      sourceMode,
      file,
      videoUrl,
      jobId,
      loading,
      error,
      enableSpeech,
      cefrLevel,
      videoLanguage,
      ttsLanguage,
      clipNotice,
    } = this.state
    const submitEnabled = this.submitEnabled
    const loadingLabel =
      sourceMode === 'url' && loading
        ? '正在下载视频…'
        : loading
          ? '提交中…'
          : sourceMode === 'url'
            ? '下载并开始生成'
            : '生成我的素材'
    const clipDialog = clipNotice
      ? buildQuotaClipNotice({
          lang: 'zh',
          sourceDurationSec: clipNotice.sourceDurationSec,
          processedDurationSec: clipNotice.processedDurationSec,
          reasons: clipNotice.reasons,
        })
      : null

    return (
      <>
        <div className="rounded-2xl border border-white/80 bg-white/90 p-6 shadow-[0_8px_30px_rgba(0,0,0,0.06)] backdrop-blur-sm">
          <UploadForm
            sourceMode={sourceMode}
            onSourceModeChange={(mode) => this.setState({ sourceMode: mode, error: null })}
            file={file}
            onFileChange={(f) => this.setState({ file: f })}
            videoUrl={videoUrl}
            onVideoUrlChange={(url) => this.setState({ videoUrl: url })}
            disabled={loading || Boolean(jobId)}
          />

          <div className="my-6 grid gap-3 sm:grid-cols-2">
            <label className="flex items-center gap-2 text-sm sm:col-span-2">
              <input
                type="checkbox"
                checked={enableSpeech}
                disabled={Boolean(jobId)}
                onChange={(e) => this.setState({ enableSpeech: e.target.checked })}
              />
              生成解说声道（旁白配音）
            </label>
            <label className="text-sm">
              CEFR
              <select
                className="mt-1 w-full rounded border border-zinc-300 px-2 py-1 dark:border-zinc-600 dark:bg-zinc-800"
                value={cefrLevel}
                disabled={Boolean(jobId)}
                onChange={(e) => this.setState({ cefrLevel: e.target.value })}
              >
                {['A1', 'A2', 'B1', 'B2', 'C1'].map((level) => (
                  <option key={level} value={level}>
                    {level}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm">
              当前视频语言（ASR）
              <select
                className="mt-1 w-full rounded border border-zinc-300 px-2 py-1 dark:border-zinc-600 dark:bg-zinc-800"
                value={videoLanguage}
                disabled={Boolean(jobId)}
                onChange={(e) => this.setState({ videoLanguage: e.target.value })}
              >
                {VIDEO_LANGUAGES.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm">
              解说声道语言
              <select
                className="mt-1 w-full rounded border border-zinc-300 px-2 py-1 dark:border-zinc-600 dark:bg-zinc-800"
                value={ttsLanguage}
                disabled={Boolean(jobId) || !enableSpeech}
                onChange={(e) => this.setState({ ttsLanguage: e.target.value })}
              >
                {TTS_LANGUAGES.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="flex flex-col items-stretch gap-3 sm:flex-row sm:items-center">
            <button
              type="button"
              onClick={this.handleCreateJob}
              disabled={!submitEnabled || loading || Boolean(jobId)}
              className="inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-[#86efac] to-[#4ade80] px-6 py-3 text-sm font-semibold text-white shadow-md transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {loadingLabel}
            </button>
          </div>

          {error && (
            <p className="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
              {error}
            </p>
          )}

          {loading && sourceMode === 'url' && (
            <p className="mt-4 rounded-lg border border-violet-200 bg-violet-50 px-3 py-2 text-sm text-violet-900 dark:border-violet-900 dark:bg-violet-950/40 dark:text-violet-200">
              正在从链接下载视频到服务器，请稍候（长视频可能需要几分钟）…
            </p>
          )}

          {jobId && (
            <JobPanel
              jobId={jobId}
              onClear={() => {
                this.props.onClearJob?.()
                this.setState({
                  jobId: null,
                  file: null,
                  videoUrl: '',
                  sourceMode: 'file',
                  error: null,
                  clipNotice: null,
                })
              }}
            />
          )}
        </div>

        {clipDialog && (
          <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
            role="presentation"
            onClick={() => this.setState({ clipNotice: null })}
          >
            <div
              role="dialog"
              aria-modal="true"
              aria-labelledby="quota-clip-title"
              className="w-full max-w-md rounded-3xl border border-amber-200 bg-white p-6 shadow-xl"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="text-xs font-medium uppercase tracking-wider text-amber-600">
                额度提示
              </div>
              <h2
                id="quota-clip-title"
                className="mt-2 text-xl font-bold tracking-tight text-[#166534]"
              >
                {clipDialog.title}
              </h2>
              <p className="mt-3 text-sm leading-relaxed text-[#4a5568]">{clipDialog.intro}</p>
              <ul className="mt-4 list-disc space-y-2 pl-5 text-sm leading-relaxed text-[#4a5568]">
                {clipDialog.reasonLines.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
              <p className="mt-4 text-xs leading-relaxed text-[#718096]">{clipDialog.footer}</p>
              <button
                type="button"
                onClick={() => this.setState({ clipNotice: null })}
                className="mt-6 w-full rounded-2xl bg-[#166534] py-2.5 text-sm font-semibold text-white transition hover:bg-[#14532d]"
              >
                我知道了
              </button>
            </div>
          </div>
        )}
      </>
    )
  }
}
