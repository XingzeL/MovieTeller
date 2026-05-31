import { BrowserRouter, Route, Routes } from 'react-router-dom'

import { StartPage } from './components/StartPage'
import { Dashboard } from './components/Dashboard'
import { StudyCardPage } from './components/StudyCardPage'
import { Workspace } from './Workspace'

/**
 * App
 *
 * Top-level router configuration.
 * This is now a pure declarative routing layer — no more in-memory view state machine.
 *
 * Routes:
 *   /           → StartPage (public landing / marketing)
 *   /dashboard  → Dashboard (history, credits, create entry point)
 *   /create     → Workspace in "new job" mode (upload form)
 *   /jobs/:jobId → Workspace in "existing job" mode (progress + progressive previews + downloads)
 *   /study-cards/:jobId → Full-page study-card reader from history
 *
 * All navigation (browser back/forward, refresh, direct links, deep links) now works correctly.
 */
export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public landing / marketing page */}
        <Route path="/" element={<StartPage />} />

        {/* Main authenticated-style workspace hub */}
        <Route path="/dashboard" element={<Dashboard />} />

        {/* Create a brand new video + narration + study cards */}
        <Route path="/create" element={<Workspace />} />

        {/* Deep link or continue an existing job (progress, previews, download) */}
        <Route path="/jobs/:jobId" element={<Workspace />} />

        {/* Full-page study card reader for completed history items */}
        <Route path="/study-cards/:jobId" element={<StudyCardPage />} />

        {/* Unknown routes gracefully fall back to the dashboard */}
        <Route path="*" element={<Dashboard />} />
      </Routes>
    </BrowserRouter>
  )
}
