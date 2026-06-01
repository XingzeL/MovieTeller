import { useAuth, useUser } from '@clerk/clerk-react'

import { getClerkInstanceHost } from '../auth/clerkInstance'
import { isClerkEnabled } from '../auth/clerkConfig'

/**
 * Dev helper: shows which Clerk instance this build talks to and current session.
 */
export function ClerkAuthDiagnostics() {
  if (!isClerkEnabled() || !import.meta.env.DEV) return null

  const host = getClerkInstanceHost()
  const { isLoaded, isSignedIn, userId } = useAuth()
  const { user } = useUser()

  const emails =
    user?.emailAddresses?.map((e) => e.emailAddress).join(', ') || '—'

  return (
    <div className="max-w-md rounded-lg border border-[#86efac] bg-white/90 px-3 py-2 text-left text-xs text-[#475569] shadow-sm">
      <div className="font-semibold text-[#166534]">Clerk 诊断（仅开发）</div>
      <div className="mt-1 break-all">
        实例：<code className="text-[#166534]">{host ?? '未知'}</code>
      </div>
      <div className="mt-1">
        Dashboard 请在 <strong>Development</strong> 下打开<strong>该实例</strong>的 Users（应用名可能叫
        NarraLingo，以实例域名为准）。
      </div>
      <div className="mt-1">
        当前会话：{!isLoaded ? '加载中…' : isSignedIn ? `已登录 ${userId}` : '未登录'}
      </div>
      {isSignedIn && (
        <div className="mt-1 break-all">
          邮箱：{emails}
          <div className="text-[#166534]">
            若此处有邮箱但 Dashboard 搜不到 → 看错实例或看错 Development/Production。
          </div>
        </div>
      )}
    </div>
  )
}
