// src/pages/Dashboard.tsx
// Live teacher dashboard — shows idle card when no session is active,
// full monitoring UI when a session is running.

import { useEffect, useState, useRef } from 'react'
import { useWebSocket }   from '../hooks/useWebSocket'
import { useApi }         from '../hooks/useApi'
import { useAuth }        from '../contexts/AuthContext'
import { StudentCard }    from '../components/StudentCard'
import { QAPanel }        from '../components/QAPanel'
import { AlertsLog }      from '../components/AlertsLog'
import { AttentionChart } from '../components/AttentionChart'
import { SessionSetup }   from '../components/SessionSetup'
import { CollectiveAlert } from '../components/CollectiveAlert'
import { StudentModal }   from '../components/StudentModal'
import { AttendanceLiveList } from '../components/AttendanceLiveList'
import type { Session }   from '../types'

interface HistoryPoint { time: string; attention: number }

function attentionColor(pct: number): string {
  if (pct >= 75) return 'color-green'
  if (pct >= 50) return 'color-yellow'
  return 'color-red'
}

export function Dashboard() {
  const [session,      setSession]      = useState<Session | null>(null)
  const [isPaused,     setIsPaused]     = useState(false)
  const [history,      setHistory]      = useState<HistoryPoint[]>([])
  const [selectedRoll, setSelectedRoll] = useState<number | null>(null)
  const [showSetup,    setShowSetup]    = useState(false)
  const [confirmEnd,   setConfirmEnd]   = useState(false)
  const historyRef = useRef<HistoryPoint[]>([])

  const api      = useApi()
  const { user } = useAuth()

  // Fetch any already-active session on mount (no auto-popup)
  useEffect(() => {
    api.getActiveSesion().then(s => { if (s) setSession(s) })
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const { telemetry, status, alerts, clearAlerts } = useWebSocket(
    session?.session_id ?? ''
  )

  const lastHistTs = useRef<string>('')
  useEffect(() => {
    if (!telemetry || telemetry.timestamp === lastHistTs.current) return
    lastHistTs.current = telemetry.timestamp
    const pt = { time: telemetry.timestamp, attention: telemetry.class_attention_pct }
    historyRef.current = [...historyRef.current.slice(-119), pt]
    setHistory([...historyRef.current])
    setIsPaused(telemetry.is_paused || false)
  }, [telemetry])

  async function handleCreateSession(
    subject: string, start: string, end: string,
    teacher: string, div: string, room: string,
  ) {
    const s = await api.createSession(subject, start, end, teacher, div, room)
    if (s) {
      setSession(s)
      setShowSetup(false)
    }
  }

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

  async function handleEndSession() {
    if (!session) return
    await api.endSession(session.session_id)
    setSession(null)
    setHistory([])
    historyRef.current = []
    setIsPaused(false)
    setConfirmEnd(false)
  }

  const qa            = telemetry?.qa_window
  const faces         = telemetry?.faces ?? []
  const classPct      = telemetry?.class_attention_pct ?? 0
  const wrongRoll     = qa?.wrong_student ? qa.speaker_roll : null
  const collectiveAlert = telemetry?.collective_alert || false

  // ── IDLE STATE — no active session ───────────────────────────────────────
  if (!session) {
    return (
      <>
        {showSetup && (
          <SessionSetup onStart={handleCreateSession} loading={api.loading} initialTeacher={user?.name ?? ''} />
        )}

        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100%',
          padding: 40,
        }}>
          <div style={{
            background: 'var(--card-bg)',
            border: '1px solid var(--border)',
            borderRadius: 20,
            padding: '56px 64px',
            textAlign: 'center',
            maxWidth: 480,
            width: '100%',
            boxShadow: '0 8px 40px rgba(0,0,0,0.3)',
          }}>
            <div style={{ fontSize: 56, marginBottom: 16 }}>📋</div>
            <h2 style={{ margin: '0 0 10px', fontSize: 24, fontWeight: 700 }}>
              No Active Session
            </h2>
            <p style={{ color: 'var(--text-muted)', fontSize: 14, margin: '0 0 32px', lineHeight: 1.6 }}>
              {user?.name ? `Welcome, ${user.name}.` : ''} Start a new session to begin monitoring
              student attention in real time.
            </p>
            <button
              className="btn btn-primary"
              style={{ padding: '14px 32px', fontSize: 16, fontWeight: 700, borderRadius: 10 }}
              onClick={() => setShowSetup(true)}
            >
              + Start New Session
            </button>

            {api.error && (
              <div style={{
                marginTop: 20,
                color: 'var(--red)',
                fontSize: 13,
                background: 'rgba(239,68,68,0.08)',
                border: '1px solid var(--red)',
                borderRadius: 8,
                padding: '10px 16px',
              }}>
                {api.error}
              </div>
            )}
          </div>
        </div>
      </>
    )
  }

  // ── ACTIVE SESSION — live monitoring UI ──────────────────────────────────
  return (
    <div style={{ display: 'flex', height: '100%' }}>

      {collectiveAlert && <CollectiveAlert onDismiss={handleResume} />}

      {selectedRoll !== null && (
        <StudentModal rollNo={selectedRoll} onClose={() => setSelectedRoll(null)} />
      )}

      {/* Confirm End Session Dialog */}
      {confirmEnd && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
        }}>
          <div style={{
            background: 'var(--card-bg)',
            border: '1px solid var(--border)',
            borderRadius: 16,
            padding: '36px 40px',
            maxWidth: 400,
            width: '100%',
            textAlign: 'center',
            boxShadow: '0 16px 48px rgba(0,0,0,0.5)',
          }}>
            <div style={{ fontSize: 40, marginBottom: 12 }}>⚠️</div>
            <h3 style={{ margin: '0 0 12px', fontSize: 20 }}>End this session?</h3>
            <p style={{ color: 'var(--text-muted)', fontSize: 14, margin: '0 0 28px' }}>
              This will stop monitoring and save all recorded data. This cannot be undone.
            </p>
            <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
              <button
                className="btn"
                style={{ padding: '10px 24px' }}
                onClick={() => setConfirmEnd(false)}
              >
                Cancel
              </button>
              <button
                className="btn"
                style={{ padding: '10px 24px', background: 'var(--red)', border: 'none', fontWeight: 700 }}
                onClick={handleEndSession}
              >
                End Session
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Main content ── */}
      <div style={{ flex: 1, padding: 24, overflowY: 'auto' }}>

        {/* Session Banner */}
        <div style={{
          background: 'var(--card-bg)',
          border: '1px solid var(--border)',
          borderRadius: 12,
          padding: '16px 24px',
          marginBottom: 24,
          display: 'flex',
          alignItems: 'center',
          gap: 32,
          flexWrap: 'wrap',
        }}>
          <div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1 }}>Subject</div>
            <div style={{ fontWeight: 700, fontSize: 18 }}>{session.subject_name}</div>
          </div>
          <div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1 }}>Teacher</div>
            <div style={{ fontWeight: 600 }}>{session.teacher_name}</div>
          </div>
          <div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1 }}>Division</div>
            <div style={{ fontWeight: 600 }}>Div {session.class_div}</div>
          </div>
          <div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1 }}>Room</div>
            <div style={{ fontWeight: 600 }}>{session.room_no}</div>
          </div>
          <div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1 }}>Time</div>
            <div style={{ fontWeight: 600, fontSize: 13 }}>
              {new Date(session.scheduled_start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              {' → '}
              {new Date(session.scheduled_end).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </div>
          </div>

          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 12 }}>
            <div className={`header-status ${status}`}>{status}</div>
            {isPaused
              ? <button className="btn btn-resume" onClick={handleResume}>▶ Resume</button>
              : <button className="btn btn-pause"  onClick={handlePause}>⏸ Pause</button>
            }
            <button
              className="btn"
              style={{ background: 'var(--red)', border: 'none', fontWeight: 700 }}
              onClick={() => setConfirmEnd(true)}
            >
              End Session
            </button>
          </div>
        </div>

        {isPaused && (
          <div style={{
            background: 'rgba(245,158,11,0.1)', border: '1px solid var(--yellow)',
            borderRadius: 10, padding: '12px 20px', marginBottom: 20,
            color: 'var(--yellow)', fontWeight: 600, textAlign: 'center',
          }}>
            ⏸️ Session Paused — Intermission active. Student scores are not being recorded.
          </div>
        )}

        {/* Stat Row */}
        <div className="stat-row">
          <div className="stat-card">
            <div className="stat-label">Class Attention</div>
            <div className={`stat-value ${attentionColor(classPct)}`}>
              {Math.round(classPct)}<span style={{ fontSize: 18 }}>%</span>
            </div>
            <div className="stat-sub">{faces.length} faces tracked</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Drowsy</div>
            <div className={`stat-value ${faces.filter(f => f.is_drowsy).length > 0 ? 'color-red' : 'color-green'}`}>
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
        <div style={{ marginTop: 24 }}>
          <div className="section-title" style={{ fontSize: 16, marginBottom: 14 }}>
            Live Student Attention — Div {session.class_div}
          </div>
          {faces.length === 0 ? (
            <div style={{
              background: 'var(--card-bg)', border: '1px dashed var(--border)',
              borderRadius: 12, padding: '40px 20px', textAlign: 'center',
              color: 'var(--text-muted)',
            }}>
              <div style={{ fontSize: 32, marginBottom: 8 }}>📷</div>
              No faces detected yet.<br />
              <span style={{ fontSize: 13 }}>Make sure the webcam pipeline is running: <code>python scripts/run_full_pipeline.py</code></span>
            </div>
          ) : (
            <div className="student-grid">
              {faces.map(face => (
                <StudentCard
                  key={face.roll_no}
                  face={face}
                  isWrongSpeaker={face.roll_no === wrongRoll}
                  onClick={() => setSelectedRoll(face.roll_no)}
                />
              ))}
            </div>
          )}
        </div>

        <div style={{ marginTop: 24 }}>
          <AttentionChart history={history} />
        </div>
      </div>

      {/* ── Right Sidebar ── */}
      <aside className="app-sidebar">
        <QAPanel qa={qa ?? {
          active: false, asked_roll: null, question_text: null,
          seconds_remaining: 0, speaker_roll: null, wrong_student: false,
        }} />
        <hr style={{ border: 'none', borderTop: '1px solid var(--border)' }} />
        <AlertsLog alerts={alerts} onClear={clearAlerts} />
        <AttendanceLiveList sessionId={session.session_id} telemetry={telemetry} />
      </aside>

    </div>
  )
}
