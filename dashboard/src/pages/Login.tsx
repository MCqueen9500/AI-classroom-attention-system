// src/pages/Login.tsx
// Teacher / Admin authentication page.

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

export function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError]       = useState('')
  const [busy, setBusy]         = useState(false)

  const navigate  = useNavigate()
  const { login } = useAuth()

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      })
      if (res.ok) {
        const data = await res.json() as {
          token: string
          is_admin: boolean
          name: string
          username: string
          subject?: string
          division?: string
        }
        // Store in context + localStorage
        login(data.token, {
          username: data.username,
          name: data.name,
          is_admin: data.is_admin,
          subject: data.subject,
          division: data.division,
        })
        // Route based on role
        navigate(data.is_admin ? '/admin' : '/dashboard', { replace: true })
      } else {
        const body = await res.json().catch(() => ({}))
        setError((body as { detail?: string }).detail ?? 'Invalid username or password')
      }
    } catch {
      setError('Connection failed — is the backend running?')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div style={{
      display: 'flex',
      height: '100vh',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'var(--bg-dark)',
    }}>
      <div style={{
        background: 'var(--card-bg)',
        border: '1px solid var(--border)',
        padding: 40,
        borderRadius: 14,
        width: 360,
        boxShadow: '0 20px 60px rgba(0,0,0,0.5)',
      }}>
        <h2 style={{ marginBottom: 4, color: 'var(--accent)', fontWeight: 800, fontSize: 26 }}>
          ClassMon
        </h2>
        <p style={{ color: 'var(--text-muted)', marginBottom: 28, fontSize: 13, margin: '0 0 28px' }}>
          Classroom Attention Monitor — Sign In
        </p>

        <form onSubmit={handleLogin} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <label style={{ fontSize: 12, display: 'flex', flexDirection: 'column', gap: 6 }}>
            <span style={{ color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.5 }}>Username</span>
            <input
              autoFocus
              autoComplete="username"
              value={username}
              onChange={e => setUsername(e.target.value)}
              style={{
                background: 'var(--bg-dark)',
                color: 'white',
                border: '1px solid var(--border)',
                padding: '10px 12px',
                borderRadius: 8,
                fontSize: 14,
                outline: 'none',
              }}
            />
          </label>

          <label style={{ fontSize: 12, display: 'flex', flexDirection: 'column', gap: 6 }}>
            <span style={{ color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.5 }}>Password</span>
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              style={{
                background: 'var(--bg-dark)',
                color: 'white',
                border: '1px solid var(--border)',
                padding: '10px 12px',
                borderRadius: 8,
                fontSize: 14,
                outline: 'none',
              }}
            />
          </label>

          {error && (
            <div style={{
              color: 'var(--red)',
              fontSize: 13,
              background: 'rgba(239,68,68,0.1)',
              border: '1px solid var(--red)',
              borderRadius: 6,
              padding: '8px 12px',
            }}>
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={busy || !username.trim() || !password.trim()}
            className="btn btn-primary"
            style={{ padding: '12px', marginTop: 8, fontSize: 15, fontWeight: 700 }}
          >
            {busy ? 'Signing in…' : 'Login'}
          </button>
        </form>
      </div>
    </div>
  )
}
