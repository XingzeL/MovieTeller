import type { ReactNode } from 'react'
import { useEffect, useLayoutEffect } from 'react'
import { useAuth } from '@clerk/clerk-react'

import { clearDevSession, setBearerTokenProvider } from '../api/apiClient'

type Props = {
  children: ReactNode
}

/**
 * Waits for Clerk session, registers getToken for apiFetch, then renders children.
 * Prevents protected API calls before Bearer is available.
 */
export function ClerkApiAuthBridge({ children }: Props) {
  const { isLoaded, isSignedIn, getToken } = useAuth()

  useLayoutEffect(() => {
    if (!isLoaded) {
      setBearerTokenProvider(null)
      return
    }
    setBearerTokenProvider(async () => {
      try {
        return (await getToken()) ?? null
      } catch {
        return null
      }
    })
    return () => setBearerTokenProvider(null)
  }, [isLoaded, getToken, isSignedIn])

  useEffect(() => {
    if (!isLoaded || !isSignedIn) return
    void clearDevSession()
  }, [isLoaded, isSignedIn])

  if (!isLoaded) {
    return (
      <div className="flex min-h-dvh items-center justify-center bg-[#f0fdf4] text-[#718096]">
        加载中…
      </div>
    )
  }

  return children
}
