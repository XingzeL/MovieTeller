import { useEffect, useRef, useState } from 'react'

import { apiFetch } from '../api/apiClient'

type Props = {
  jobId: string
  version: string
  onUnavailable: () => void
  className?: string
}

/** Loads job thumbnail via apiFetch (Bearer or dev cookie), not a bare img URL. */
export function JobThumbnail({ jobId, version, onUnavailable, className }: Props) {
  const [objectUrl, setObjectUrl] = useState<string | null>(null)
  const onUnavailableRef = useRef(onUnavailable)
  onUnavailableRef.current = onUnavailable

  useEffect(() => {
    let cancelled = false
    let blobUrl: string | null = null

    const load = async () => {
      setObjectUrl(null)
      const res = await apiFetch(
        `/api/jobs/${encodeURIComponent(jobId)}/thumbnail?v=${encodeURIComponent(version)}`,
      )
      if (cancelled) return
      if (!res.ok) {
        onUnavailableRef.current()
        return
      }
      const blob = await res.blob()
      if (cancelled) return
      blobUrl = URL.createObjectURL(blob)
      setObjectUrl(blobUrl)
    }

    void load()

    return () => {
      cancelled = true
      if (blobUrl) URL.revokeObjectURL(blobUrl)
    }
    // onUnavailable is read via ref; omit from deps to avoid reload on parent re-render.
  }, [jobId, version])

  if (!objectUrl) {
    return (
      <div className="flex h-full w-full items-center justify-center text-sm font-semibold text-[#166534] opacity-70">
        …
      </div>
    )
  }

  return (
    <img
      src={objectUrl}
      alt=""
      className={className}
    />
  )
}
