import { VideoSourceTabs, type VideoSourceMode } from '../modules/videoUpload'

type UploadFormProps = {
  sourceMode: VideoSourceMode
  onSourceModeChange: (mode: VideoSourceMode) => void
  file: File | null
  onFileChange: (file: File | null) => void
  videoUrl: string
  onVideoUrlChange: (url: string) => void
  /** 提交生成中等场景下禁用上传与输入 */
  disabled?: boolean
}

export function UploadForm({
  sourceMode,
  onSourceModeChange,
  file,
  onFileChange,
  videoUrl,
  onVideoUrlChange,
  disabled = false,
}: UploadFormProps) {
  return (
    <VideoSourceTabs
      mode={sourceMode}
      onModeChange={onSourceModeChange}
      file={file}
      onFileChange={onFileChange}
      videoUrl={videoUrl}
      onVideoUrlChange={onVideoUrlChange}
      disabled={disabled}
    />
  )
}
