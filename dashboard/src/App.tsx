import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Dashboard } from './pages/Dashboard'
import { Login } from './pages/Login'
import { Registration } from './pages/Registration'
import { Link, useNavigate } from 'react-router-dom'

function StudentLayout() {
  const navigate = useNavigate()
  return (
    <div className="layout" style={{ display: 'block', padding: 0 }}>
      <header className="app-header">
        <div className="header-logo">ClassMon</div>
        <div style={{ display: 'flex', gap: 16, marginLeft: 20 }}>
          <Link to="/dashboard" style={{ color: 'var(--text-dim)', textDecoration: 'none', fontWeight: 600 }}>Dashboard</Link>
          <Link to="/students" style={{ color: 'var(--accent)', textDecoration: 'none', fontWeight: 600 }}>Students</Link>
        </div>
        <div style={{ flex: 1 }}></div>
        <button className="btn" onClick={() => {
          localStorage.removeItem('classmon_token')
          navigate('/login')
        }}>Logout</button>
      </header>
      <main style={{ padding: 24, height: 'calc(100vh - 56px)', overflowY: 'auto' }}>
        <Registration />
      </main>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/login" element={<Login />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/students" element={<StudentLayout />} />
      </Routes>
    </BrowserRouter>
  )
}
