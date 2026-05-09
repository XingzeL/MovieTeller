import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type ChangeEvent,
  type DragEvent,
} from 'react'
import { MAX_VIDEO_BYTES, VIDEO_ACCEPT } from './constants'
import { formatBytes, validateMp4File } from './utils'

export type VideoUploadProps = {
  /** 当前选中的本地视频文件 */
  file: File | null
  onFileChange: (file: File | null) => void
  /** 禁用交互（例如提交中） */
  disabled?: boolean
}

/**
 * 本地视频上传：选择文件 / 拖拽、大小与格式提示、可选预览。
 * 独立模块，供表单页组合使用。
 */
export function VideoUpload({ file, onFileChange, disabled = false }: VideoUploadProps) {
  const inputId = useId()
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragOver, setDragOver] = useState(false)
  const [hint, setHint] = useState<string | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)

  useEffect(() => {
    if (!file) {
      setPreviewUrl(null)
      return
    }
    const url = URL.createObjectURL(file)
    setPreviewUrl(url)
    return () => {
      URL.revokeObjectURL(url)
    }
  }, [file])

  const applyFile = useCallback(
    (next: File | null) => {
      setHint(null)
      if (!next) {
        onFileChange(null)
        if (inputRef.current) inputRef.current.value = ''
        return
      }
      const err = validateMp4File(next)
      if (err) {
        setHint(err)
        return
      }
      onFileChange(next)
    },
    [onFileChange]
  )

  const onInputChange = (e: ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0] ?? null
    applyFile(f)
  }

  const onDrop = (e: DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    if (disabled) return
    const f = e.dataTransfer.files?.[0] ?? null
    applyFile(f)
  }

  const onDragOver = (e: DragEvent) => {
    e.preventDefault()
    if (!disabled) setDragOver(true)
  }

  const onDragLeave = () => setDragOver(false)

  return (
    <div className="space-y-3">
      <span className="mb-1.5 block text-sm font-medium text-zinc-700 dark:text-zinc-300">
        上传 MP4 视频
      </span>

      <input
        ref={inputRef}
        type="file"
        accept={VIDEO_ACCEPT}
        disabled={disabled}
        className="sr-only"
        onChange={onInputChange}
        id={inputId}
      />

      <div
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            if (!disabled) inputRef.current?.click()
          }
        }}
        onClick={() => !disabled && inputRef.current?.click()}
        onDrop={onDrop}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        className={`rounded-xl border-2 border-dashed px-4 py-8 text-center transition ${
          disabled
            ? 'cursor-not-allowed border-zinc-200 bg-zinc-100 opacity-60 dark:border-zinc-700 dark:bg-zinc-900'
            : dragOver
              ? 'cursor-pointer border-violet-500 bg-violet-50 dark:border-violet-400 dark:bg-violet-950/30'
              : 'cursor-pointer border-zinc-300 bg-white hover:border-violet-400 dark:border-zinc-600 dark:bg-zinc-900'
        }`}
      >
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          拖拽视频到此处，或点击选择文件
        </p>
        <p className="mt-1 text-xs text-zinc-500">
          仅支持 MP4，最大约 {formatBytes(MAX_VIDEO_BYTES)}
        </p>
      </div>

      {hint && (
        <p className="text-sm text-amber-700 dark:text-amber-300">{hint}</p>
      )}

      {file && (
        <div className="flex flex-col gap-2 rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-2 text-left text-sm dark:border-zinc-700 dark:bg-zinc-900/80">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="font-medium text-zinc-800 dark:text-zinc-100">{file.name}</span>
            <span className="text-zinc-500">{formatBytes(file.size)}</span>
          </div>
          <button
            type="button"
            disabled={disabled}
            onClick={(e) => {
              e.stopPropagation()
              applyFile(null)
            }}
            className="self-start text-xs text-violet-600 underline hover:text-violet-500 disabled:opacity-50 dark:text-violet-400"
          >
            清除选择
          </button>
        </div>
      )}

      {previewUrl && file && (
        <div className="overflow-hidden rounded-lg border border-zinc-200 bg-black dark:border-zinc-700">
          <video
            src={previewUrl}
            controls
            className="max-h-64 w-full object-contain"
            preload="metadata"
          >
            您的浏览器不支持视频预览
          </video>
        </div>
      )}
    </div>
  )
}
