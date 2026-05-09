import { Component } from 'react'
import { UploadForm } from './components/UploadForm'
import type { InputMode } from './components/UploadForm'
import { LevelSelector } from './components/LevelSelector'
import { ResultDisplay } from './components/ResultDisplay'
import type { GenerateResponse, NarrationLevel } from './types'

function canSubmit(
  mode: InputMode,
  url: string,
  file: File | null,
  levels: NarrationLevel[]
) {
  if (levels.length === 0) return false
  if (mode === 'url') return url.trim().length > 0
  return file !== null
}

type UploadPageState = {
  mode: InputMode
  url: string
  file: File | null
  levels: NarrationLevel[]
  results: Partial<Record<NarrationLevel, string>> | null
  loading: boolean
  error: string | null
}

/** 上传与生成流程：URL/文件、等级选择、提交与结果展示，由类组件集中管理状态与请求。 */
export default class UploadPage extends Component<object, UploadPageState> {
  state: UploadPageState = {
    mode: 'url',
    url: '',
    file: null,
    levels: [],
    results: null,
    loading: false,
    error: null,
  }

  private get submitEnabled(): boolean {
    const { mode, url, file, levels } = this.state
    return canSubmit(mode, url, file, levels)
  }

  private handleGenerate = async () => {
    const { mode, url, file, levels, loading } = this.state
    if (!canSubmit(mode, url, file, levels) || loading) return
    this.setState({ error: null, loading: true, results: null })
    try {
      let res: Response
      if (mode === 'url') {
        res = await fetch('/api/generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            type: 'url',
            levels,
            input: url.trim(),
          }),
        })
      } else {
        const fd = new FormData()
        fd.append('type', 'file')
        fd.append('levels', JSON.stringify(levels))
        if (file) fd.append('file', file)
        res = await fetch('/api/generate', {
          method: 'POST',
          body: fd,
        })
      }
      const data = (await res.json()) as GenerateResponse & { error?: string }
      if (!res.ok) {
        this.setState({
          error: data.error ?? `Request failed (${res.status})`,
          loading: false,
        })
        return
      }
      this.setState({ results: data.results ?? null, loading: false })
    } catch {
      this.setState({
        error: 'Network error. Is the server running on port 3001?',
        loading: false,
      })
    }
  }

  render() {
    const { mode, url, file, levels, loading, error, results } = this.state
    const submitEnabled = this.submitEnabled

    return (
      <>
        <div className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
          <UploadForm
            mode={mode}
            onModeChange={(m) => {
              this.setState({ mode: m, error: null })
            }}
            url={url}
            onUrlChange={(v) => this.setState({ url: v })}
            file={file}
            onFileChange={(f) => this.setState({ file: f })}
            disabled={loading}
          />

          <div className="my-8 border-t border-zinc-100 dark:border-zinc-800" />

          <LevelSelector
            selected={levels}
            onChange={(next) => this.setState({ levels: next })}
          />

          <div className="mt-8 flex flex-col items-stretch gap-3 sm:flex-row sm:items-center">
            <button
              type="button"
              onClick={this.handleGenerate}
              disabled={!submitEnabled || loading}
              className="inline-flex items-center justify-center gap-2 rounded-xl bg-violet-600 px-6 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-violet-500 disabled:cursor-not-allowed disabled:bg-zinc-300 disabled:text-zinc-500 dark:disabled:bg-zinc-700 dark:disabled:text-zinc-400"
            >
              {loading && (
                <svg
                  className="size-4 animate-spin"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                  aria-hidden
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
              )}
              {loading ? 'Generating…' : 'Generate'}
            </button>
            {!submitEnabled && !loading && (
              <p className="text-center text-xs text-zinc-500 sm:text-left">
                Add a URL or file and pick at least one level.
              </p>
            )}
          </div>

          {error && (
            <p className="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
              {error}
            </p>
          )}
        </div>

        <ResultDisplay results={results} orderedLevels={levels} />
      </>
    )
  }
}
