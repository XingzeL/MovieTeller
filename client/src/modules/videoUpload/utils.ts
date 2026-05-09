import { MAX_VIDEO_BYTES } from './constants'

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / (1024 * 1024)).toFixed(1)} MB`
}

export function validateMp4File(file: File): string | null {
  const looksMp4 =
    file.name.toLowerCase().endsWith('.mp4') || file.type === 'video/mp4'
  if (!looksMp4) {
    return '请上传 MP4 文件（.mp4）'
  }
  if (file.size > MAX_VIDEO_BYTES) {
    return `文件过大（最大 ${formatBytes(MAX_VIDEO_BYTES)}）`
  }
  return null
}
