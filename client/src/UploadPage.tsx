import { Component } from 'react'

import { JobPanel } from './components/JobPanel'
import { UploadForm } from './components/UploadForm'
import type { CreateJobResponse } from './types/job'

function jobIdFromUrl(): string | null {
  const raw = new URLSearchParams(window.location.search).get('jobId')
  return raw?.trim() ? raw.trim() : null
}

const VIDEO_LANGUAGES = [
  { value: 'auto', label: '自动检测' },
  { value: 'en', label: '英语' },
  { value: 'zh', label: '中文' },
  { value: 'ja', label: '日语' },
  { value: 'ko', label: '韩语' },
  { value: 'fr', label: '法语' },
  { value: 'de', label: '德语' },
  { value: 'es', label: '西班牙语' },
]

const TTS_LANGUAGES = [
  { value: 'en', label: '英语' },
  { value: 'zh', label: '中文' },
  { value: 'ja', label: '日语' },
  { value: 'ko', label: '韩语' },
  { value: 'fr', label: '法语' },
  { value: 'de', label: '德语' },
  { value: 'es', label: '西班牙语' },
]

type UploadPageState = {
  file: File | null
  jobId: string | null
  enablePolish: boolean
  enableSpeech: boolean
  enableSubtitleContext: boolean
  cefrLevel: string
  videoLanguage: string
  ttsLanguage: string
  loading: boolean
  error: string | null
}

/** 上传视频并创建后台 Job；支持 URL 查询参数恢复 jobId。 */
export default class UploadPage extends Component<object, UploadPageState> {
  state: UploadPageState = {
    file: null,
    jobId: jobIdFromUrl(),
    enablePolish: true,
    enableSpeech: true,
    enableSubtitleContext: true,
    cefrLevel: 'B1',
    videoLanguage: 'auto',
    ttsLanguage: 'en',
    loading: false,
    error: null,
  }

  private get submitEnabled(): boolean {
    return this.state.file !== null && !this.state.loading
  }

  private handleCreateJob = async () => {
    const { file, loading } = this.state
    if (!file || loading) return
    this.setState({ error: null, loading: true })
    try {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('enablePolish', this.state.enablePolish ? 'true' : 'false')
      fd.append('enableSpeech', this.state.enableSpeech ? 'true' : 'false')
      fd.append('enableSubtitleContext', this.state.enableSubtitleContext ? 'true' : 'false')
      fd.append('enableEmbedVideo', 'true')
      fd.append('cefrLevel', this.state.cefrLevel)
      fd.append('sourceLanguage', this.state.videoLanguage)
      fd.append('ttsLanguage', this.state.ttsLanguage)
      fd.append('narrationLanguage', this.state.ttsLanguage)
      fd.append('subtitleLanguage', this.state.videoLanguage)
      const res = await fetch('/api/jobs', { method: 'POST', body: fd })
      const data = (await res.json()) as CreateJobResponse & { error?: string }
      if (!res.ok) {
        this.setState({
          error: data.error ?? `Request failed (${res.status})`,
          loading: false,
        })
        return
      }
      const nextJobId = data.jobId
      const params = new URLSearchParams(window.location.search)
      params.set('jobId', nextJobId)
      window.history.replaceState({}, '', `?${params}`)
      this.setState({ jobId: nextJobId, loading: false })
    } catch {
      this.setState({
        error: 'Network error. Is the server running on port 3001?',
        loading: false,
      })
    }
  }

  render() {
    const {
      file,
      jobId,
      loading,
      error,
      enablePolish,
      enableSpeech,
      enableSubtitleContext,
      cefrLevel,
      videoLanguage,
      ttsLanguage,
    } = this.state
    const submitEnabled = this.submitEnabled

    return (
      <>
        <div className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
          <UploadForm
            file={file}
            onFileChange={(f) => this.setState({ file: f })}
            disabled={loading || Boolean(jobId)}
          />

          <div className="my-6 grid gap-3 sm:grid-cols-2">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={enablePolish}
                disabled={Boolean(jobId)}
                onChange={(e) => this.setState({ enablePolish: e.target.checked })}
              />
              润色
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={enableSpeech}
                disabled={Boolean(jobId)}
                onChange={(e) => this.setState({ enableSpeech: e.target.checked })}
              />
              TTS
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={enableSubtitleContext}
                disabled={Boolean(jobId)}
                onChange={(e) =>
                  this.setState({ enableSubtitleContext: e.target.checked })
                }
              />
              字幕上下文
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
              TTS 语言
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
              className="inline-flex items-center justify-center gap-2 rounded-xl bg-violet-600 px-6 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-violet-500 disabled:cursor-not-allowed disabled:bg-zinc-300 disabled:text-zinc-500 dark:disabled:bg-zinc-700 dark:disabled:text-zinc-400"
            >
              {loading ? '提交中…' : '创建 Job'}
            </button>
          </div>

          {error && (
            <p className="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
              {error}
            </p>
          )}

          {jobId && (
            <JobPanel
              jobId={jobId}
              onClear={() => {
                const params = new URLSearchParams(window.location.search)
                params.delete('jobId')
                window.history.replaceState(
                  {},
                  '',
                  params.toString() ? `?${params}` : window.location.pathname
                )
                this.setState({
                  jobId: null,
                  file: null,
                  error: null,
                })
              }}
            />
          )}
        </div>
      </>
    )
  }
}
