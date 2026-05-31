import { apiFetch } from './apiClient'

export class ArtifactDownloadError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ArtifactDownloadError'
    this.status = status
  }
}

function triggerBlobDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  try {
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = filename
    anchor.rel = 'noopener'
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
  } finally {
    URL.revokeObjectURL(url)
  }
}

function filenameFromDisposition(header: string | null, fallback: string): string {
  if (!header) return fallback
  const match = /filename\*?=(?:UTF-8''|")?([^";]+)/i.exec(header)
  if (!match?.[1]) return fallback
  try {
    return decodeURIComponent(match[1].replace(/"/g, '').trim())
  } catch {
    return match[1].replace(/"/g, '').trim() || fallback
  }
}

/**
 * Download rendered video via authenticated fetch (required for 410 handling).
 */
export async function downloadRenderedVideo(jobId: string): Promise<void> {
  const res = await apiFetch(
    `/api/jobs/${encodeURIComponent(jobId)}/artifacts/renderedVideo`,
  )
  if (!res.ok) {
    let message = `下载失败 (${res.status})`
    try {
      const body = (await res.json()) as { error?: string }
      if (body.error) message = body.error
    } catch {
      /* ignore non-json */
    }
    throw new ArtifactDownloadError(message, res.status)
  }
  const blob = await res.blob()
  const name = filenameFromDisposition(
    res.headers.get('Content-Disposition'),
    `narrated-${jobId}.mp4`,
  )
  triggerBlobDownload(blob, name)
}
