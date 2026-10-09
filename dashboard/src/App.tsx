// src/App.tsx
// Root of the application: wraps everything in AuthProvider,
// adds ProtectedRoute, and registers all page routes.

import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useEffect, useState }   from 'react'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import { Dashboard }             from './pages/Dashboard'
import { Login }                 from './pages/Login'
import { Admin }                 from './pages/Admin'
import { Registration }          from './pages/Registration'
import { Analytics }             from './pages/Analytics'
import { History }               from './pages/History'
import { Roster }                from './pages/Roster'
import { Navbar }                from './components/Navbar'
import { Sidebar }               from './components/Sidebar'
import { useWebSocket }          from './hooks/useWebSocket'
import { useApi }                from './hooks/useApi'
import type { Session }          from './types'

// ── Main Layout (teacher views) ───────────────────────────────────────────────

function MainLayout({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const api = useApi()

  useEffect(() => {
    api.getActiveSesion().then(s => { if (s) setSession(s) })
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const { status } = useWebSocket(session?.session_id ?? '')
  const { user }   = useAuth()

  return (
    <div className="layout" style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <Navbar
        sessionName={session?.subject_name}
        sessionStart={session?.scheduled_start}
        sessionEnd={session?.scheduled_end}
        status={status}
        teacherName={user?.name}
      />
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        <Sidebar />
        <main style={{ flex: 1, overflowY: 'auto', background: 'var(--bg-dark)' }}>
          {children}
        </main>
      </div>
    </div>
  )
}

// ── Protected Route ───────────────────────────────────────────────────────────

interface ProtectedRouteProps {
  children: React.ReactNode
  /** If true, only admins may visit this route */
  adminOnly?: boolean
  /** If true, only non-admins (teachers) may visit this route */
  teacherOnly?: boolean
}

function ProtectedRoute({ children, adminOnly, teacherOnly }: ProtectedRouteProps) {
  const { user, loading } = useAuth()

  // While restoring session, render nothing (or a spinner)
  if (loading) {
    return (
      <div style={{
        height: '100vh', display: 'flex',
        alignItems: 'center', justifyContent: 'center',
        background: 'var(--bg-dark)', color: 'var(--text-muted)',
        fontSize: 14,
      }}>
        Loading…
      </div>
    )
  }

  // Not authenticated → login
  if (!user) return <Navigate to="/login" replace />

  // Admin trying to access teacher-only route → admin panel
  if (teacherOnly && user.is_admin) return <Navigate to="/admin" replace />

  // Non-admin trying to access admin-only route → dashboard
  if (adminOnly && !user.is_admin) return <Navigate to="/dashboard" replace />

  return <>{children}</>
}

// ── App (routes) ──────────────────────────────────────────────────────────────

function AppRoutes() {
  return (
    <Routes>
      {/* Default redirect */}
      <Route path="/" element={<Navigate to="/dashboard" replace />} />

      {/* Public */}
      <Route path="/login" element={<Login />} />

      {/* Admin-only */}
      <Route
        path="/admin"
        element={
          <ProtectedRoute adminOnly>
            <Admin />
          </ProtectedRoute>
        }
      />

      {/* Teacher routes — protected + redirect admins away */}
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute teacherOnly>
            <MainLayout><Dashboard /></MainLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/analytics"
        element={
          <ProtectedRoute teacherOnly>
            <MainLayout><Analytics /></MainLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/history"
        element={
          <ProtectedRoute teacherOnly>
            <MainLayout><History /></MainLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/roster"
        element={
          <ProtectedRoute teacherOnly>
            <MainLayout><Roster /></MainLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/students"
        element={
          <ProtectedRoute teacherOnly>
            <MainLayout><div style={{ padding: 24 }}><Registration /></div></MainLayout>
          </ProtectedRoute>
        }
      />
    </Routes>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  )
}
