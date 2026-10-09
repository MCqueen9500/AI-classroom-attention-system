import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useApi } from '../hooks/useApi'
import type { Session } from '../types'

export function History() {
  const [sessions, setSessions] = useState<Session[]>([])
  const api = useApi()
  const navigate = useNavigate()

  useEffect(() => {
    api.listSessions().then(res => { if(res) setSessions(res) })
  }, []) // eslint-disable-line

  function formatDuration(start: string, end: string) {
    const s = new Date(start).getTime()
    const e = new Date(end).getTime()
    const mins = Math.round((e - s) / 60000)
    return `${mins} mins`
  }

  return (
    <div className="page-container">
      <div className="section-title">Session History</div>
      
      {api.loading && <div>Loading sessions...</div>}
      
      <div className="session-grid" style={{ display: 'grid', gap: 16, gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))' }}>
        {sessions.map(s => (
          <div
            key={s.session_id}
            style={{
              padding: 20,
              cursor: 'pointer',
              background: 'var(--surface)',
              border: s.is_active ? '2px solid var(--accent)' : '1px solid var(--border)',
              borderRadius: 12,
              transition: 'transform 0.15s, box-shadow 0.15s',
              boxShadow: '0 2px 12px rgba(0,0,0,0.2)',
            }}
            onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-2px)'; e.currentTarget.style.boxShadow = '0 6px 20px rgba(0,0,0,0.35)' }}
            onMouseLeave={e => { e.currentTarget.style.transform = 'none'; e.currentTarget.style.boxShadow = '0 2px 12px rgba(0,0,0,0.2)' }}
            onClick={() => navigate('/analytics', { state: { sessionId: s.session_id } })}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
              <h3 style={{ margin: 0 }}>{s.subject_name}</h3>
              {s.is_active && <span style={{ background: 'var(--accent)', color: '#fff', padding: '2px 8px', borderRadius: 12, fontSize: 11, fontWeight: 'bold' }}>LIVE</span>}
            </div>
            
            <div style={{ color: 'var(--text-dim)', fontSize: 14, marginBottom: 8 }}>
              {new Date(s.scheduled_start).toLocaleDateString()} at {new Date(s.scheduled_start).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
            </div>
            
            <div style={{ display: 'flex', gap: 16, fontSize: 13, color: '#aaa', marginTop: 16 }}>
              <div>⏱ {formatDuration(s.scheduled_start, s.scheduled_end)}</div>
            </div>
          </div>
        ))}
        {sessions.length === 0 && !api.loading && (
          <div style={{ color: 'var(--text-dim)' }}>No sessions recorded yet.</div>
        )}
      </div>
    </div>
  )
}
