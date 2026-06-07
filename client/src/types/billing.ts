export type MockPurchaseResponse = {
  ok: boolean
  kind: 'plan' | 'addon'
  id: string
  planCode?: string | null
  addedProcessingMinutes: number
  addedNarrationMinutes: number
  processingRemainingMinutes: number
  narrationRemainingMinutes: number
}
