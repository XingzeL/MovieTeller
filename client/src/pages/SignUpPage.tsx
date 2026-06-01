import { SignUp } from '@clerk/clerk-react'
import { Link } from 'react-router-dom'

import { isClerkEnabled } from '../auth/clerkConfig'
import { ClerkAuthDiagnostics } from '../components/ClerkAuthDiagnostics'

export function SignUpPage() {
  if (!isClerkEnabled()) {
    return (
      <div className="flex min-h-dvh flex-col items-center justify-center gap-4 p-8">
        <p className="text-[#166534]">开发模式：请配置 Clerk 密钥，或使用 ?asUser= 联调。</p>
        <Link to="/dashboard" className="text-sm text-[#4b5563] underline">
          返回 Dashboard（dev）
        </Link>
      </div>
    )
  }

  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-4 bg-[#f0fdf4] p-6">
      <SignUp
        routing="path"
        path="/sign-up"
        signInUrl="/sign-in"
        fallbackRedirectUrl="/dashboard"
      />
      <ClerkAuthDiagnostics />
    </div>
  )
}
