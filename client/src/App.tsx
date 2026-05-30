import { useCallback, useEffect, useState } from 'react'

import UploadPage from './UploadPage'
import { StartPage } from './components/StartPage'

function jobIdFromUrl(): string | null {
  const raw = new URLSearchParams(window.location.search).get('jobId')
  return raw?.trim() ? raw.trim() : null
}

function setJobIdInUrl(jobId: string | null) {
  const params = new URLSearchParams(window.location.search)
  if (jobId) {
    params.set('jobId', jobId)
  } else {
    params.delete('jobId')
  }
  const qs = params.toString()
  window.history.replaceState({}, '', qs ? `?${qs}` : window.location.pathname)
}

export default function App() {
  const [showFunctionalApp, setShowFunctionalApp] = useState(false)
  const [jobId, setJobId] = useState<string | null>(() => jobIdFromUrl())

  useEffect(() => {
    const onPopState = () => setJobId(jobIdFromUrl())
    window.addEventListener('popstate', onPopState)
    return () => window.removeEventListener('popstate', onPopState)
  }, [])

  const selectJob = useCallback((nextId: string) => {
    setJobIdInUrl(nextId)
    setJobId(nextId)
    setShowFunctionalApp(true) // 进入功能页
  }, [])

  const clearJob = useCallback(() => {
    setJobIdInUrl(null)
    setJobId(null)
  }, [])

  // 如果还没进入功能页，显示 Start Page
  if (!showFunctionalApp) {
    return <StartPage onEnter={() => setShowFunctionalApp(true)} />
  }

  // 进入功能页（原有的上传 + Job 面板）
  return (
    <div className="min-h-dvh text-[var(--text-dark)] bg-[#f0fdf4]">
      <div className="mx-auto max-w-2xl px-4 py-12 sm:px-6">
        <header className="mb-10 text-center">
          <div className="flex items-center justify-center gap-3">
            <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tighter text-transparent bg-clip-text bg-gradient-to-r from-[#86efac] to-[#4ade80]">
              NarraLingo
            </h1>
            <button 
              onClick={() => {
                setShowFunctionalApp(false)
                clearJob()
              }}
              className="text-xs px-3 py-1 rounded-full bg-[#d1fae5] hover:bg-[#bbf7d0] border border-[#86efac] text-[#166534] font-medium transition-colors"
            >
              Back to Home
            </button>
          </div>
          <p className="mt-2 text-sm font-medium text-[#4a5568]">
            Upload videos to generate narrated tracks + language learning materials
          </p>
        </header>

        <UploadPage jobId={jobId} onJobIdChange={selectJob} onClearJob={clearJob} />
      </div>
    </div>
  )
}
