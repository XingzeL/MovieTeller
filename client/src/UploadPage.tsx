import { Component } from 'react'

import { apiFetch, ensureDevSession } from './api/apiClient'
import { parseVideoUrl, type ParsedVideo } from './api/parseVideo'
import { JobPanel } from './components/JobPanel'
import { UploadForm } from './components/UploadForm'
import type { VideoSourceMode } from './modules/videoUpload'
import { VideoParsePreview, validateVideoUrl } from './modules/videoUpload'
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
  if (input.code === 'video_parse_failed') {
    return '无法解析该视频链接。请确认链接为公开可访问，或改用本地上传。'
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
  parsedVideo: ParsedVideo | null
  urlParsing: boolean
  parseError: string | null
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
    parsedVideo: null,
    urlParsing: false,
    parseError: null,
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
    return (
      validateVideoUrl(this.state.videoUrl) === null &&
      this.state.parsedVideo != null &&
      Boolean(
        this.state.parsedVideo.title?.trim() ||
          this.state.parsedVideo.id?.trim() ||
          this.state.parsedVideo.platform?.trim()
      )
    )
  }

  private get submitDisabledReason(): string | null {
    if (this.state.sourceMode !== 'url' || this.submitEnabled) return null
    if (validateVideoUrl(this.state.videoUrl) !== null) {
      return '请输入有效的视频链接（暂不支持 YouTube）'
    }
    if (this.state.urlParsing) return '正在解析视频信息…'
    if (!this.state.parsedVideo) {
      return '请先点击「解析链接」，确认视频信息后再提交'
    }
    return null
  }

  private handleParseUrl = async () => {
    const { videoUrl, urlParsing, loading } = this.state
    if (urlParsing || loading) return
    const urlErr = validateVideoUrl(videoUrl)
    if (urlErr) {
      this.setState({ parseError: urlErr, parsedVideo: null })
      return
    }
    this.setState({ urlParsing: true, parseError: null, parsedVideo: null, error: null })
    try {
      await ensureDevSession()
      const parsed = await parseVideoUrl(
        (input, init) => apiFetch(input, init),
        videoUrl.trim()
      )
      this.setState({ parsedVideo: parsed, urlParsing: false })
    } catch (err) {
      const message =
        err instanceof Error ? err.message : '解析失败，请稍后重试或改用本地上传。'
      this.setState({ parseError: message, urlParsing: false, parsedVideo: null })
    }
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
      parsedVideo,
      urlParsing,
      parseError,
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
    const submitDisabledReason = this.submitDisabledReason
    const loadingLabel =
      sourceMode === 'url' && loading
        ? '正在创建任务…'
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
            onSourceModeChange={(mode) =>
              this.setState({
                sourceMode: mode,
                error: null,
                parsedVideo: null,
                parseError: null,
              })
            }
            file={file}
            onFileChange={(f) => this.setState({ file: f })}
            videoUrl={videoUrl}
            onVideoUrlChange={(url) =>
              this.setState({ videoUrl: url, parsedVideo: null, parseError: null })
            }
            onParseUrl={this.handleParseUrl}
            urlParsing={urlParsing}
            disabled={loading || Boolean(jobId)}
          />

          {sourceMode === 'url' && (
            <div className="mt-4 space-y-3">
              <VideoParsePreview
                parsed={parsedVideo}
                parsing={urlParsing}
                parseError={parseError}
              />
              {!parsedVideo && !urlParsing && !parseError && validateVideoUrl(videoUrl) === null && (
                <p className="text-xs text-zinc-500 dark:text-zinc-400">
                  请先点击「解析链接」确认视频信息；任务创建后将在后台下载，可在任务列表查看进度。
                </p>
              )}
            </div>
          )}

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
            {!submitEnabled && submitDisabledReason && !jobId && (
              <p className="text-sm text-amber-700 dark:text-amber-300 sm:flex-1 sm:self-center">
                {submitDisabledReason}
              </p>
            )}
          </div>

          {error && (
            <p className="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
              {error}
            </p>
          )}

          {loading && sourceMode === 'url' && (
            <p className="mt-4 rounded-lg border border-violet-200 bg-violet-50 px-3 py-2 text-sm text-violet-900 dark:border-violet-900 dark:bg-violet-950/40 dark:text-violet-200">
              正在创建任务…视频将在后台下载，请稍后在任务列表查看「下载中」状态。
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
                  parsedVideo: null,
                  parseError: null,
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
