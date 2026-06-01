export function getClerkPublishableKey(): string | undefined {
  const key = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY?.trim()
  return key || undefined
}

export function isClerkEnabled(): boolean {
  return Boolean(getClerkPublishableKey())
}
