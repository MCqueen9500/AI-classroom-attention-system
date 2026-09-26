import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useApi } from '../hooks/useApi'

export function Login() {
  const [username, setUsername] = useState('admin')
  const [password, setPassword] = useState('password')
  const [error, setError] = useState('')
  const navigate = useNavigate()
  const api = useApi()

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault()
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      })
      if (res.ok) {
        const data = await res.json()
        localStorage.setItem('classmon_token', data.token)
        localStorage.setItem('classmon_teacher', data.name)
        navigate('/dashboard')
      } else {
        setError('Invalid username or password')
      }
    } catch (err) {
      setError('Connection failed')
    }
  }

  return (
    <div style={{ display: 'flex', height: '100vh', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ background: 'var(--surface)', padding: 40, borderRadius: 14, width: 360, boxShadow: 'var(--shadow)' }}>
        <h2 style={{ marginBottom: 8, color: 'var(--accent)' }}>ClassMon</h2>
        <p style={{ color: 'var(--text-dim)', marginBottom: 24, fontSize: 13 }}>Teacher Authentication</p>
        
        <form onSubmit={handleLogin} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <label style={{ fontSize: 12, display: 'flex', flexDirection: 'column', gap: 4 }}>
            Username
            <input 
              value={username} onChange={e => setUsername(e.target.value)} 
              style={{ background: 'var(--bg)', color: 'white', border: '1px solid var(--border)', padding: '10px', borderRadius: 6 }}
            />
          </label>
          <label style={{ fontSize: 12, display: 'flex', flexDirection: 'column', gap: 4 }}>
            Password
            <input 
              type="password" value={password} onChange={e => setPassword(e.target.value)} 
              style={{ background: 'var(--bg)', color: 'white', border: '1px solid var(--border)', padding: '10px', borderRadius: 6 }}
            />
          </label>
          
          {error && <div style={{ color: 'var(--red)', fontSize: 12 }}>{error}</div>}
          
          <button type="submit" className="btn btn-primary" style={{ padding: 12, marginTop: 8 }}>
            Login
          </button>
        </form>
      </div>
    </div>
  )
}
