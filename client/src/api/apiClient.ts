const DEV_USER_STORAGE_KEY = 'movieteller.devUserId'

function readDevUserFromQuery(): string | null {
  if (typeof window === 'undefined') return null
  const params = new URLSearchParams(window.location.search)
  const asUser = params.get('asUser')?.trim()
  return asUser || null
}

export function getDevUserId(): string | null {
  if (typeof window === 'undefined') return null
  const fromQuery = readDevUserFromQuery()
  if (fromQuery) {
    window.localStorage.setItem(DEV_USER_STORAGE_KEY, fromQuery)
    return fromQuery
  }
  return window.localStorage.getItem(DEV_USER_STORAGE_KEY)
}

export async function ensureDevSession(): Promise<void> {
  const userId = getDevUserId()
  if (!userId) return
  await apiFetch('/api/dev/session', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ userId }),
  })
}

export async function apiFetch(
  input: string,
  init: RequestInit = {},
): Promise<Response> {
  const headers = new Headers(init.headers)
  return fetch(input, {
    ...init,
    headers,
    credentials: 'include',
  })
}
