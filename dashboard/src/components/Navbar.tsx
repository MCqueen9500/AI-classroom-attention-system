import { useAuth } from '../contexts/AuthContext'

interface NavbarProps {
  sessionName?: string
  sessionStart?: string
  sessionEnd?: string
  status?: string
  teacherName?: string
}

export function Navbar({ sessionName, sessionStart, sessionEnd, status, teacherName }: NavbarProps) {
  const { logout } = useAuth()

  return (
    <header className="app-header">
      <div className="header-logo">ClassMon</div>

      {sessionName && (
        <div className="header-session" style={{ marginLeft: 30, flex: 1 }}>
          <span style={{ fontWeight: 600 }}>{sessionName}</span>
          <span style={{ color: 'var(--text-muted)', marginLeft: 10 }}>
            {sessionStart && new Date(sessionStart).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            {' – '}
            {sessionEnd && new Date(sessionEnd).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>
        </div>
      )}

      {!sessionName && <div style={{ flex: 1 }} />}

      {teacherName && (
        <span style={{ fontSize: 13, color: 'var(--text-muted)', marginRight: 8 }}>
          👤 {teacherName}
        </span>
      )}

      {status && <div className={`header-status ${status}`}>{status}</div>}

      <button className="btn" style={{ marginLeft: 12 }} onClick={logout}>
        Logout
      </button>
    </header>
  )
}
