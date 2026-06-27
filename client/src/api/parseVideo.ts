export type ParsedVideo = {
  sourceUrl: string
  id?: string | null
  title?: string | null
  thumbnail?: string | null
  duration?: number | null
  platform?: string | null
  uploader?: string | null
}

export async function parseVideoUrl(
  fetchFn: (input: string, init?: RequestInit) => Promise<Response>,
  sourceUrl: string
): Promise<ParsedVideo> {
  const res = await fetchFn('/api/videos/parse', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sourceUrl }),
  })
  const data = (await res.json()) as ParsedVideo & { error?: string; code?: string }
  if (!res.ok) {
    const err = new Error(data.error || `parse failed (${res.status})`)
    ;(err as Error & { code?: string }).code = data.code
    throw err
  }
  return data
}
