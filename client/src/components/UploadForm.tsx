import { VideoUpload } from '../modules/videoUpload'

export type InputMode = 'url' | 'file'

type UploadFormProps = {
  mode: InputMode
  onModeChange: (mode: InputMode) => void
  url: string
  onUrlChange: (url: string) => void
  file: File | null
  onFileChange: (file: File | null) => void
  /** 提交生成中等场景下禁用上传与输入 */
  disabled?: boolean
}

export function UploadForm({
  mode,
  onModeChange,
  url,
  onUrlChange,
  file,
  onFileChange,
  disabled = false,
}: UploadFormProps) {
  return (
    <div className="space-y-4">
      <div className="flex gap-2 rounded-lg border border-zinc-200 bg-zinc-50 p-1 dark:border-zinc-700 dark:bg-zinc-900">
        <button
          type="button"
          disabled={disabled}
          onClick={() => onModeChange('url')}
          className={`flex-1 rounded-md px-3 py-2 text-sm font-medium transition disabled:opacity-50 ${
            mode === 'url'
              ? 'bg-white text-zinc-900 shadow-sm dark:bg-zinc-800 dark:text-zinc-100'
              : 'text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100'
          }`}
        >
          Video URL
        </button>
        <button
          type="button"
          disabled={disabled}
          onClick={() => onModeChange('file')}
          className={`flex-1 rounded-md px-3 py-2 text-sm font-medium transition disabled:opacity-50 ${
            mode === 'file'
              ? 'bg-white text-zinc-900 shadow-sm dark:bg-zinc-800 dark:text-zinc-100'
              : 'text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100'
          }`}
        >
          Upload MP4
        </button>
      </div>

      {mode === 'url' ? (
        <label className="block">
          <span className="mb-1.5 block text-sm font-medium text-zinc-700 dark:text-zinc-300">
            Paste a YouTube or direct video link
          </span>
          <input
            type="url"
            value={url}
            disabled={disabled}
            onChange={(e) => onUrlChange(e.target.value)}
            placeholder="https://..."
            className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2.5 text-zinc-900 placeholder:text-zinc-400 focus:border-violet-500 focus:outline-none focus:ring-2 focus:ring-violet-500/20 disabled:opacity-60 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100"
          />
        </label>
      ) : (
        <VideoUpload file={file} onFileChange={onFileChange} disabled={disabled} />
      )}
    </div>
  )
}
