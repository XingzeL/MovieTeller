import { UserButton } from '@clerk/clerk-react'

import { isClerkEnabled } from '../auth/clerkConfig'

type Props = {
  devLabel: string
}

const userButtonAppearance = {
  elements: {
    rootBox: 'w-full',
    userButtonBox: 'flex w-full flex-row items-center gap-3 justify-start',
    userButtonTrigger:
      'w-full rounded-xl py-1.5 hover:bg-[#f0fdf4] focus:shadow-none focus:ring-0',
    userButtonOuterIdentifier: 'font-medium text-[#166534] text-sm truncate',
    userButtonAvatarBox: 'h-8 w-8 shrink-0',
    userButtonPopoverCard: 'rounded-xl border border-[#d1fae5] shadow-lg',
    userButtonPopoverActionButton: 'hover:bg-[#f0fdf4]',
    userButtonPopoverActionButtonText: 'text-[#166534]',
    userButtonPopoverActionButtonIcon: 'text-[#166534]',
    userPreviewMainIdentifier: 'text-[#166534]',
    userPreviewSecondaryIdentifier: 'text-[#718096]',
  },
}

/**
 * Sidebar footer: Clerk UserButton (profile, switch account, sign out) or dev label.
 */
export function DashboardSidebarUser({ devLabel }: Props) {
  if (isClerkEnabled()) {
    return (
      <div className="w-full">
        <UserButton showName afterSignOutUrl="/" appearance={userButtonAppearance} />
        <div className="mt-0.5 pl-11 text-xs text-[#718096]">Free Plan</div>
      </div>
    )
  }

  return (
    <div className="flex items-center gap-3">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-[#86efac] to-[#4ade80] text-sm font-semibold text-white">
        U
      </div>
      <div className="min-w-0 text-sm">
        <div className="truncate font-medium text-[#166534]">{devLabel}</div>
        <div className="text-xs text-[#718096]">Free Plan</div>
      </div>
    </div>
  )
}
