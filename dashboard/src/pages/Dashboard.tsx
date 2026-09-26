// src/App.tsx
// Main dashboard — connects WebSocket, renders all panels

import { useEffect, useState, useRef } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useWebSocket }  from '../hooks/useWebSocket'
import { useApi }        from '../hooks/useApi'
import { StudentCard }   from '../components/StudentCard'
import { QAPanel }       from '../components/QAPanel'
import { AlertsLog }     from '../components/AlertsLog'
import { AttentionChart} from '../components/AttentionChart'
import { SessionSetup }  from '../components/SessionSetup'
import type { Session }  from '../types'

interface HistoryPoint { time: string; attention: number }

function attentionColor(pct: number): string {
  if (pct >= 75) return 'color-green'
  if (pct >= 50) return 'color-yellow'
  return 'color-red'
}

export function Dashboard() {
  const [session,  setSession]  = useState<Session | null>(null)
  const [isPaused, setIsPaused] = useState(false)
  const [history,  setHistory]  = useState<HistoryPoint[]>([])
  const historyRef = useRef<HistoryPoint[]>([])

  const api = useApi()
  const navigate = useNavigate()

  useEffect(() => {
    const token = localStorage.getItem('classmon_token')
    if (!token) {
      navigate('/login')
      return
    }
    api.getActiveSesion().then(s => { if (s) setSession(s) })
  }, [])  // eslint-disable-line

  // WebSocket connection
  const { telemetry, status, alerts, clearAlerts } = useWebSocket(
    session?.session_id ?? ''
  )

  // Accumulate attention history for the chart (one point per second max)
  const lastHistTs = useRef<string>('')
  useEffect(() => {
    if (!telemetry || telemetry.timestamp === lastHistTs.current) return
    lastHistTs.current = telemetry.timestamp
    const pt = { time: telemetry.timestamp, attention: telemetry.class_attention_pct }
    historyRef.current = [...historyRef.current.slice(-119), pt]
    setHistory([...historyRef.current])
  }, [telemetry])

  // Create session handler
  async function handleCreateSession(subject: string, start: string, end: string) {
    const s = await api.createSession(subject, start, end)
    if (s) setSession(s)
  }

  // Pause / Resume
  async function handlePause() {
    if (!session) return
    await api.pauseSession(session.session_id)
    setIsPaused(true)
  }
  async function handleResume() {
    if (!session) return
    await api.resumeSession(session.session_id)
    setIsPaused(false)
  }

  const qa   = telemetry?.qa_window
  const faces = telemetry?.faces ?? []
  const classPct = telemetry?.class_attention_pct ?? 0

  // Find which face is wrong speaker
  const wrongRoll = qa?.wrong_student ? qa.speaker_roll : null

  // Show session setup if no session
  if (!session) {
    return (
      <>
        <SessionSetup onStart={handleCreateSession} loading={api.loading} />
        {api.error && (
          <div style={{ position:'fixed', bottom:20, left:'50%', transform:'translateX(-50%)',
            background:'var(--red)', color:'#fff', padding:'8px 20px', borderRadius:8 }}>
            {api.error}
          </div>
        )}
      </>
    )
  }

  return (
    <div className="layout">

      {/* ── Header ── */}
      <header className="app-header">
        <div className="header-logo">ClassMon</div>
        <div style={{ display: 'flex', gap: 16, marginLeft: 20 }}>
          <Link to="/dashboard" style={{ color: 'var(--accent)', textDecoration: 'none', fontWeight: 600 }}>Dashboard</Link>
          <Link to="/students" style={{ color: 'var(--text-dim)', textDecoration: 'none', fontWeight: 600 }}>Students</Link>
        </div>
        <div className="header-session">
          {session.subject_name} &nbsp;·&nbsp;
          <span style={{ color:'var(--text-dim)' }}>
            {new Date(session.scheduled_start).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}
            {' – '}
            {new Date(session.scheduled_end).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}
          </span>
        </div>

        <div className={`header-status ${status}`}>{status}</div>

        {isPaused
          ? <button className="btn btn-resume" onClick={handleResume}>Resume</button>
          : <button className="btn btn-pause"  onClick={handlePause}>Pause</button>
        }

        {isPaused && (
          <div style={{ fontSize:12, color:'var(--yellow)', fontWeight:600 }}>
            PAUSED — Intermission active
          </div>
        )}
      </header>

      {/* ── Main ── */}
      <main className="app-main">

        {/* Stat Row */}
        <div className="stat-row">
          <div className="stat-card">
            <div className="stat-label">Class Attention</div>
            <div className={`stat-value ${attentionColor(classPct)}`}>
              {Math.round(classPct)}<span style={{fontSize:18}}>%</span>
            </div>
            <div className="stat-sub">{faces.length} students tracked</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Drowsy</div>
            <div className={`stat-value ${faces.filter(f=>f.is_drowsy).length > 0 ? 'color-red' : 'color-green'}`}>
              {faces.filter(f => f.is_drowsy).length}
            </div>
            <div className="stat-sub">students drowsy now</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Q&amp;A Window</div>
            <div className={`stat-value ${qa?.active ? 'color-accent' : 'color-green'}`}>
              {qa?.active ? `${Math.ceil(qa.seconds_remaining)}s` : '--'}
            </div>
            <div className="stat-sub">{qa?.active ? `Roll ${qa.asked_roll}` : 'No active window'}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Alerts</div>
            <div className={`stat-value ${alerts.length > 0 ? 'color-red' : 'color-green'}`}>
              {alerts.length}
            </div>
            <div className="stat-sub">unread alerts</div>
          </div>
        </div>

        {/* Student Grid */}
        <div>
          <div className="section-title">Live Student Attention</div>
          {faces.length === 0 ? (
            <div style={{ color:'var(--text-dim)', padding:'20px 0' }}>
              No faces detected — ensure webcam pipeline is running.
            </div>
          ) : (
            <div className="student-grid">
              {faces.map(face => (
                <StudentCard
                  key={face.roll_no}
                  face={face}
                  isWrongSpeaker={face.roll_no === wrongRoll}
                  onClick={() => {}}
                />
              ))}
            </div>
          )}
        </div>

        {/* Attention Chart */}
        <AttentionChart history={history} />

      </main>

      {/* ── Sidebar ── */}
      <aside className="app-sidebar">
        <QAPanel qa={qa ?? { active:false, asked_roll:null, question_text:null,
          seconds_remaining:0, speaker_roll:null, wrong_student:false }} />
        <hr style={{ border:'none', borderTop:'1px solid var(--border)' }} />
        <AlertsLog alerts={alerts} onClear={clearAlerts} />
      </aside>

    </div>
  )
}
