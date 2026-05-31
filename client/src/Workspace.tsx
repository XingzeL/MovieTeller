import { useNavigate, useParams } from 'react-router-dom'

import UploadPage from './UploadPage'

/**
 * Workspace
 * 
 * The main in-app area for creating videos and viewing job progress.
 * Handles both /create (new job) and /jobs/:jobId (existing job) routes.
 * 
 * This component is intentionally thin — it only manages router integration
 * and the consistent outer layout/header for the functional pages.
 */
export function Workspace() {
  const navigate = useNavigate()
  const { jobId: routeJobId } = useParams<{ jobId?: string }>()

  const resolvedJobId = routeJobId?.trim() || null

  const handleJobIdChange = (newJobId: string) => {
    // A new job was created inside UploadPage → navigate to its dedicated page.
    // Using replace so the browser back button doesn't land on a transient /create state.
    navigate(`/jobs/${newJobId}`, { replace: true })
  }

  const handleClearJob = () => {
    // User clicked "新建任务" (or equivalent) inside JobPanel.
    // Take them to a fresh creation flow.
    navigate('/create', { replace: true })
  }

  const handleBackToDashboard = () => {
    navigate('/dashboard')
  }

  return (
    <div className="min-h-dvh text-[var(--text-dark)] bg-[#f0fdf4]">
      <div className="mx-auto max-w-2xl px-4 py-12 sm:px-6">
        <header className="mb-10 text-center">
          <div className="flex items-center justify-center gap-3">
            <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tighter text-transparent bg-clip-text bg-gradient-to-r from-[#86efac] to-[#4ade80]">
              NarraLingo
            </h1>
            <button
              type="button"
              onClick={handleBackToDashboard}
              className="text-xs px-3 py-1 rounded-full bg-[#d1fae5] hover:bg-[#bbf7d0] border border-[#86efac] text-[#166534] font-medium transition-colors"
            >
              Back to Dashboard
            </button>
          </div>
          <p className="mt-2 text-sm font-medium text-[#4a5568]">
            Upload videos to generate narrated tracks + language learning materials
          </p>
        </header>

        <UploadPage
          jobId={resolvedJobId}
          onJobIdChange={handleJobIdChange}
          onClearJob={handleClearJob}
        />
      </div>
    </div>
  )
}
