import { VideoUpload } from './VideoUpload'
import { VideoUrlInput } from './VideoUrlInput'

export type VideoSourceMode = 'file' | 'url'

export type VideoSourceTabsProps = {
  mode: VideoSourceMode
  onModeChange: (mode: VideoSourceMode) => void
  file: File | null
  onFileChange: (file: File | null) => void
  videoUrl: string
  onVideoUrlChange: (url: string) => void
  onParseUrl?: () => void
  urlParsing?: boolean
  disabled?: boolean
}

const TABS: { id: VideoSourceMode; label: string; hint: string }[] = [
  { id: 'file', label: '本地上传', hint: 'MP4 文件' },
  { id: 'url', label: '视频链接', hint: '公开链接；部分平台需 cookies' },
]

export function VideoSourceTabs({
  mode,
  onModeChange,
  file,
  onFileChange,
  videoUrl,
  onVideoUrlChange,
  onParseUrl,
  urlParsing = false,
  disabled = false,
}: VideoSourceTabsProps) {
  const switchMode = (next: VideoSourceMode) => {
    if (disabled || next === mode) return
    onModeChange(next)
    if (next === 'file') {
      onVideoUrlChange('')
    } else {
      onFileChange(null)
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">添加视频</h2>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
          上传本地 MP4，或粘贴公开视频链接（解析后创建任务，下载在后台进行）
        </p>
      </div>

      <div
        className="grid w-full grid-cols-2 gap-1 rounded-xl border border-zinc-200 bg-zinc-100 p-1 dark:border-zinc-700 dark:bg-zinc-800/80"
        role="tablist"
        aria-label="视频来源"
      >
        {TABS.map((tab) => {
          const active = mode === tab.id
          return (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={active}
              disabled={disabled}
              onClick={() => switchMode(tab.id)}
              className={`rounded-lg px-3 py-2.5 text-left transition ${
                active
                  ? 'bg-white text-zinc-900 shadow-sm dark:bg-zinc-900 dark:text-zinc-100'
                  : 'text-zinc-600 hover:text-zinc-900 disabled:opacity-50 dark:text-zinc-400 dark:hover:text-zinc-200'
              }`}
            >
              <span className="block text-sm font-semibold">{tab.label}</span>
              <span
                className={`mt-0.5 block text-[11px] ${
                  active ? 'text-zinc-500 dark:text-zinc-400' : 'text-zinc-400 dark:text-zinc-500'
                }`}
              >
                {tab.hint}
              </span>
            </button>
          )
        })}
      </div>

      <div role="tabpanel">
        {mode === 'file' ? (
          <VideoUpload file={file} onFileChange={onFileChange} disabled={disabled} />
        ) : (
          <VideoUrlInput
            videoUrl={videoUrl}
            onVideoUrlChange={onVideoUrlChange}
            onParseUrl={onParseUrl}
            urlParsing={urlParsing}
            disabled={disabled}
          />
        )}
      </div>
    </div>
  )
}
