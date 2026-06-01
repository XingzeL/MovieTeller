import { isClerkEnabled } from '../auth/clerkConfig'

const DEV_USER_STORAGE_KEY = 'movieteller.devUserId'

export type BearerTokenProvider = () => Promise<string | null>

let bearerTokenProvider: BearerTokenProvider | null = null

export function setBearerTokenProvider(provider: BearerTokenProvider | null) {
  bearerTokenProvider = provider
}

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

/**
 * Dev-only: write mt_uid cookie via /api/dev/session.
 * Skipped when Clerk is configured (Bearer is the identity source).
 */
export async function ensureDevSession(): Promise<void> {
  if (import.meta.env.PROD || isClerkEnabled()) return
  const userId = getDevUserId()
  if (!userId) return
  await apiFetch('/api/dev/session', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ userId }),
  })
}

/** Dev-only: drop mt_uid cookie and local ?asUser= storage (e.g. after Clerk sign-in). */
export async function clearDevSession(): Promise<void> {
  if (typeof window !== 'undefined') {
    window.localStorage.removeItem(DEV_USER_STORAGE_KEY)
  }
  if (import.meta.env.PROD) return
  try {
    await fetch('/api/dev/session', { method: 'DELETE', credentials: 'include' })
  } catch {
    /* ignore */
  }
}

export async function apiFetch(
  input: string,
  init: RequestInit = {},
): Promise<Response> {
  const headers = new Headers(init.headers)

  if (bearerTokenProvider) {
    const token = await bearerTokenProvider()
    if (token) {
      headers.set('Authorization', `Bearer ${token}`)
    }
  }

  return fetch(input, {
    ...init,
    headers,
    credentials: 'include',
  })
}
