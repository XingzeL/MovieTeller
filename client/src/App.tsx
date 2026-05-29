import { useCallback, useEffect, useState } from 'react'

import UploadPage from './UploadPage'
import { JobList } from './components/JobList'

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
  const [jobId, setJobId] = useState<string | null>(() => jobIdFromUrl())

  useEffect(() => {
    const onPopState = () => setJobId(jobIdFromUrl())
    window.addEventListener('popstate', onPopState)
    return () => window.removeEventListener('popstate', onPopState)
  }, [])

  const selectJob = useCallback((nextId: string) => {
    setJobIdInUrl(nextId)
    setJobId(nextId)
  }, [])

  const clearJob = useCallback(() => {
    setJobIdInUrl(null)
    setJobId(null)
  }, [])

  return (
    <div className="min-h-dvh bg-zinc-100 text-zinc-900 dark:bg-zinc-950 dark:text-zinc-100">
      <div className="mx-auto max-w-2xl px-4 py-12 sm:px-6">
        <header className="mb-10 text-center">
          <h1 className="text-3xl font-semibold tracking-tight text-zinc-900 dark:text-white sm:text-4xl">
            MovieTeller
          </h1>
          <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
            上传视频，后台 Job 管线生成旁白、TTS 与成片；可在下方查看任务进度与产物。
          </p>
        </header>

        <JobList selectedJobId={jobId} onSelectJob={selectJob} />
        <UploadPage jobId={jobId} onJobIdChange={selectJob} onClearJob={clearJob} />
      </div>
    </div>
  )
}
