import { BrowserRouter, Route, Routes } from 'react-router-dom'

import { AuthProvider } from './auth/AuthProvider'
import { ProtectedRoute } from './auth/ProtectedRoute'
import { StartPage } from './components/StartPage'
import { Dashboard } from './components/Dashboard'
import { StudyCardPage } from './components/StudyCardPage'
import { SignInPage } from './pages/SignInPage'
import { SignUpPage } from './pages/SignUpPage'
import { Workspace } from './Workspace'
import { PricingPage } from './pages/PricingPage'
import { UsageHistoryPage } from './pages/UsageHistoryPage'

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<StartPage />} />
          <Route path="/sign-in/*" element={<SignInPage />} />
          <Route path="/sign-up/*" element={<SignUpPage />} />

          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/create"
            element={
              <ProtectedRoute>
                <Workspace />
              </ProtectedRoute>
            }
          />
          <Route
            path="/jobs/:jobId"
            element={
              <ProtectedRoute>
                <Workspace />
              </ProtectedRoute>
            }
          />
          <Route
            path="/study-cards/:jobId"
            element={
              <ProtectedRoute>
                <StudyCardPage />
              </ProtectedRoute>
            }
          />

          {/* 定价 / 购买 Credits 页面 */}
          <Route
            path="/pricing"
            element={
              <ProtectedRoute>
                <PricingPage />
              </ProtectedRoute>
            }
          />

          {/* 使用记录 & 历史 */}
          <Route
            path="/usage"
            element={
              <ProtectedRoute>
                <UsageHistoryPage />
              </ProtectedRoute>
            }
          />

          <Route path="*" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
