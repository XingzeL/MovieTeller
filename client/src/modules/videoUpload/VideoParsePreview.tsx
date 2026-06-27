import type { ParsedVideo } from '../../api/parseVideo'

export type VideoParsePreviewProps = {
  parsed: ParsedVideo | null
  parsing: boolean
  parseError: string | null
}

function formatDuration(sec?: number | null) {
  if (!sec || sec <= 0) return '未知时长'
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}

export function VideoParsePreview({ parsed, parsing, parseError }: VideoParsePreviewProps) {
  if (parsing) {
    return (
      <p className="text-sm text-zinc-500 dark:text-zinc-400">
        正在解析视频信息…
      </p>
    )
  }

  if (parseError) {
    return (
      <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900/50 dark:bg-red-950/40 dark:text-red-300">
        {parseError}
      </p>
    )
  }

  if (!parsed) return null

  return (
    <div className="flex gap-3 rounded-xl border border-zinc-200 bg-zinc-50 p-3 dark:border-zinc-700 dark:bg-zinc-900/50">
      {parsed.thumbnail ? (
        <img
          src={parsed.thumbnail}
          alt=""
          className="h-16 w-28 shrink-0 rounded-md object-cover"
        />
      ) : null}
      <div className="min-w-0 text-sm">
        <p className="font-medium text-zinc-900 dark:text-zinc-100">
          {parsed.title || '未命名视频'}
        </p>
        <p className="mt-1 text-zinc-500 dark:text-zinc-400">
          {parsed.platform || '未知平台'} · {formatDuration(parsed.duration)}
          {parsed.uploader ? ` · ${parsed.uploader}` : ''}
        </p>
        {(!parsed.duration || parsed.duration <= 0) && (
          <p className="mt-2 text-xs text-amber-700 dark:text-amber-300">
            未能从链接预读时长；任务创建后将在下载完成时自动探测时长并校验额度。
          </p>
        )}
      </div>
    </div>
  )
}
