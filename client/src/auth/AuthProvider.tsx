import type { ReactNode } from 'react'
import { ClerkProvider } from '@clerk/clerk-react'

import { ClerkApiAuthBridge } from './ClerkApiAuthBridge'
import { getClerkPublishableKey } from './clerkConfig'

type Props = {
  children: ReactNode
}

export function AuthProvider({ children }: Props) {
  const publishableKey = getClerkPublishableKey()
  if (!publishableKey) {
    return children
  }
  return (
    <ClerkProvider publishableKey={publishableKey} afterSignOutUrl="/">
      <ClerkApiAuthBridge>{children}</ClerkApiAuthBridge>
    </ClerkProvider>
  )
}
