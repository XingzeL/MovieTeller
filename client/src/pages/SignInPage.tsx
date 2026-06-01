import { SignIn } from '@clerk/clerk-react'
import { Link } from 'react-router-dom'

import { isClerkEnabled } from '../auth/clerkConfig'
import { ClerkAuthDiagnostics } from '../components/ClerkAuthDiagnostics'

export function SignInPage() {
  if (!isClerkEnabled()) {
    return (
      <div className="flex min-h-dvh flex-col items-center justify-center gap-4 p-8">
        <p className="text-[#166534]">开发模式：请使用 URL 参数 ?asUser=user-a 或配置 Clerk 密钥。</p>
        <Link to="/dashboard" className="text-sm text-[#4b5563] underline">
          返回 Dashboard（dev）
        </Link>
      </div>
    )
  }

  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-4 bg-[#f0fdf4] p-6">
      <SignIn
        routing="path"
        path="/sign-in"
        signUpUrl="/sign-up"
        fallbackRedirectUrl="/dashboard"
      />
      <ClerkAuthDiagnostics />
    </div>
  )
}
