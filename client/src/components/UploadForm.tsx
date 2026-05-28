import { VideoUpload } from '../modules/videoUpload'

type UploadFormProps = {
  file: File | null
  onFileChange: (file: File | null) => void
  /** 提交生成中等场景下禁用上传与输入 */
  disabled?: boolean
}

export function UploadForm({ file, onFileChange, disabled = false }: UploadFormProps) {
  return <VideoUpload file={file} onFileChange={onFileChange} disabled={disabled} />
}
