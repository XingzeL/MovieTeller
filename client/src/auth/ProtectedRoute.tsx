import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { SignedIn, SignedOut } from '@clerk/clerk-react'

import { isClerkEnabled } from './clerkConfig'

type Props = {
  children: ReactNode
}

/**
 * Dev without Clerk keys: allow through (mt_uid / ensureDevSession).
 * Production or Clerk configured: require signed-in user.
 */
export function ProtectedRoute({ children }: Props) {
  const location = useLocation()

  if (!isClerkEnabled()) {
    if (import.meta.env.PROD) {
      return (
        <div className="mx-auto max-w-lg p-8 text-center text-red-700">
          <p className="font-semibold">未配置登录</p>
          <p className="mt-2 text-sm">
            生产环境需要设置 VITE_CLERK_PUBLISHABLE_KEY 与服务器 CLERK_SECRET_KEY。
          </p>
        </div>
      )
    }
    return children
  }

  return (
    <>
      <SignedIn>{children}</SignedIn>
      <SignedOut>
        <Navigate to="/sign-in" replace state={{ from: location.pathname }} />
      </SignedOut>
    </>
  )
}
