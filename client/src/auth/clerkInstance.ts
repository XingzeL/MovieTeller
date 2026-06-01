import { getClerkPublishableKey } from './clerkConfig'

function decodePublishableKeyHost(key: string): string | null {
  const encoded = key.replace(/^pk_(test|live)_/, '')
  if (!encoded || encoded === key) return null

  try {
    const normalized = encoded.replace(/-/g, '+').replace(/_/g, '/')
    const padding = '='.repeat((4 - (normalized.length % 4)) % 4)
    const decoded = window.atob(normalized + padding).replace(/\$$/, '')
    return decoded || null
  } catch {
    return null
  }
}

export function getClerkInstanceHost(): string | null {
  const key = getClerkPublishableKey()
  return key ? decodePublishableKeyHost(key) : null
}
