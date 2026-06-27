import { useId, useMemo, useState } from 'react'

import { validateVideoUrl, videoUrlHostname } from './utils'

export type VideoUrlInputProps = {
  videoUrl: string
  onVideoUrlChange: (url: string) => void
  onParseUrl?: () => void
  urlParsing?: boolean
  disabled?: boolean
}

const PLATFORM_HINTS = ['Bilibili', 'Douyin', 'TikTok', 'Vimeo']

export function VideoUrlInput({
  videoUrl,
  onVideoUrlChange,
  onParseUrl,
  urlParsing = false,
  disabled = false,
}: VideoUrlInputProps) {
  const inputId = useId()
  const [hint, setHint] = useState<string | null>(null)
  const hostname = useMemo(() => videoUrlHostname(videoUrl), [videoUrl])
  const isValid = videoUrl.trim().length > 0 && validateVideoUrl(videoUrl) === null

  const onChange = (next: string) => {
    setHint(null)
    onVideoUrlChange(next)
  }

  const onBlur = () => {
    if (!videoUrl.trim()) {
      setHint(null)
      return
    }
    const err = validateVideoUrl(videoUrl)
    setHint(err)
  }

  return (
    <div className="space-y-3">
      <div
        className={`rounded-xl border-2 border-dashed px-4 py-6 transition ${
          disabled
            ? 'border-zinc-200 bg-zinc-100 opacity-60 dark:border-zinc-700 dark:bg-zinc-900'
            : isValid
              ? 'border-emerald-300 bg-emerald-50/60 dark:border-emerald-700 dark:bg-emerald-950/20'
              : 'border-zinc-300 bg-white dark:border-zinc-600 dark:bg-zinc-900'
        }`}
      >
        <div className="mb-4 text-center">
          <div className="mx-auto mb-2 flex h-10 w-10 items-center justify-center rounded-full bg-violet-100 text-violet-700 dark:bg-violet-950 dark:text-violet-300">
            <svg
              aria-hidden
              className="h-5 w-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={1.8}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"
              />
            </svg>
          </div>
          <p className="text-sm font-medium text-zinc-700 dark:text-zinc-200">粘贴公开视频链接</p>
          <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
            暂不支持 YouTube；请粘贴其他公开链接，或改用本地 MP4 上传。
          </p>
        </div>

        <label htmlFor={inputId} className="sr-only">
          视频链接
        </label>
        <input
          id={inputId}
          type="url"
          inputMode="url"
          autoComplete="off"
          placeholder="https://www.bilibili.com/video/..."
          value={videoUrl}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value)}
          onBlur={onBlur}
          className="w-full rounded-xl border border-zinc-300 bg-white px-3 py-2.5 text-sm text-zinc-800 shadow-sm outline-none transition focus:border-violet-400 focus:ring-2 focus:ring-violet-200 disabled:cursor-not-allowed disabled:opacity-60 dark:border-zinc-600 dark:bg-zinc-950 dark:text-zinc-100 dark:focus:ring-violet-900"
        />

        <div className="mt-3 flex flex-wrap justify-center gap-1.5">
          {PLATFORM_HINTS.map((name) => (
            <span
              key={name}
              className="rounded-full bg-zinc-100 px-2 py-0.5 text-[10px] font-medium text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400"
            >
              {name}
            </span>
          ))}
        </div>

        {onParseUrl && (
          <button
            type="button"
            disabled={disabled || urlParsing || !isValid}
            onClick={onParseUrl}
            className="mt-4 w-full rounded-xl border border-violet-300 bg-violet-50 px-3 py-2 text-sm font-medium text-violet-800 transition hover:bg-violet-100 disabled:cursor-not-allowed disabled:opacity-50 dark:border-violet-800 dark:bg-violet-950/40 dark:text-violet-200"
          >
            {urlParsing ? '解析中…' : '解析链接'}
          </button>
        )}
      </div>

      {hint && <p className="text-sm text-amber-700 dark:text-amber-300">{hint}</p>}

      {isValid && hostname && (
        <div className="flex flex-col gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-left text-sm dark:border-emerald-900 dark:bg-emerald-950/30">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="font-medium text-emerald-900 dark:text-emerald-100">
              已识别链接 · {hostname}
            </span>
            <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200">
              远程视频
            </span>
          </div>
          <p className="truncate text-xs text-emerald-800/80 dark:text-emerald-200/80" title={videoUrl}>
            {videoUrl.trim()}
          </p>
          <button
            type="button"
            disabled={disabled}
            onClick={() => onChange('')}
            className="self-start text-xs text-emerald-700 underline hover:text-emerald-600 disabled:opacity-50 dark:text-emerald-300"
          >
            清除链接
          </button>
        </div>
      )}
    </div>
  )
}
