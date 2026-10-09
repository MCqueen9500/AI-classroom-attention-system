import { useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { useApi } from '../hooks/useApi'
import { ScoreTable, ScoreRow } from '../components/ScoreTable'
import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { QATranscriptLog } from '../components/QATranscriptLog'
import type { Session } from '../types'

interface SessionScores {
  session_id: string
  subject_name: string
  scheduled_start: string
  student_count: number
  scores: ScoreRow[]
}

const cardStyle: React.CSSProperties = {
  background: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: 12,
  padding: 20,
  marginBottom: 24,
}

const selectStyle: React.CSSProperties = {
  background: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  padding: '8px 14px',
  color: 'var(--text)',
  fontSize: 14,
  width: '100%',
  maxWidth: 480,
  cursor: 'pointer',
}

export function Analytics() {
  const location = useLocation()
  const passedSessionId = (location.state as any)?.sessionId ?? ''

  const [sessions,         setSessions]         = useState<Session[]>([])
  const [selectedSessionId, setSelectedSessionId] = useState<string>(passedSessionId)
  const [data,             setData]             = useState<SessionScores | null>(null)
  const [loadingScores,    setLoadingScores]    = useState(false)

  const api = useApi()

  // Load session list on mount
  useEffect(() => {
    api.listSessions().then(res => {
      if (!res) return
      setSessions(res)
      // Pre-select passed session, or first in list
      if (!passedSessionId && res.length > 0) {
        setSelectedSessionId(res[0].session_id)
      }
    })
  }, []) // eslint-disable-line

  // Load scores whenever selected session changes
  useEffect(() => {
    if (!selectedSessionId) return
    setLoadingScores(true)
    setData(null)
    const token = localStorage.getItem('token')
    fetch(`/api/sessions/${selectedSessionId}/scores`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then(r => r.json())
      .then(d => { setData(d); setLoadingScores(false) })
      .catch(() => setLoadingScores(false))
  }, [selectedSessionId])

  const selectedSession = sessions.find(s => s.session_id === selectedSessionId)

  return (
    <div className="page-container">
      <div className="section-title">Session Analytics</div>

      {/* Session selector */}
      <div style={cardStyle}>
        <div style={{ fontSize: 11, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 8 }}>
          Select Session
        </div>
        <select
          style={selectStyle}
          value={selectedSessionId}
          onChange={e => setSelectedSessionId(e.target.value)}
        >
          {sessions.length === 0 && <option>No sessions yet</option>}
          {sessions.map(s => (
            <option key={s.session_id} value={s.session_id}>
              {s.subject_name} — Div {s.class_div} &nbsp;
              ({new Date(s.scheduled_start).toLocaleDateString()} {new Date(s.scheduled_start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })})
              {s.is_active ? ' 🟢 LIVE' : ''}
            </option>
          ))}
        </select>

        {selectedSession && (
          <div style={{ display: 'flex', gap: 32, marginTop: 16, flexWrap: 'wrap' }}>
            {[
              ['Subject', selectedSession.subject_name],
              ['Teacher', selectedSession.teacher_name],
              ['Room', selectedSession.room_no],
              ['Division', `Div ${selectedSession.class_div}`],
              ['Start', new Date(selectedSession.scheduled_start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })],
              ['End', new Date(selectedSession.scheduled_end).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })],
            ].map(([label, val]) => (
              <div key={label}>
                <div style={{ fontSize: 10, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: 1 }}>{label}</div>
                <div style={{ fontWeight: 600, marginTop: 2 }}>{val}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {loadingScores && (
        <div style={{ textAlign: 'center', color: 'var(--text-dim)', padding: 40 }}>
          Loading scores...
        </div>
      )}

      {data && data.scores.length === 0 && !loadingScores && (
        <div style={{ ...cardStyle, textAlign: 'center', color: 'var(--text-dim)', padding: 40 }}>
          <div style={{ fontSize: 32, marginBottom: 8 }}>📊</div>
          No student data recorded for this session yet.<br />
          <span style={{ fontSize: 13 }}>Scores appear once the vision pipeline tracks faces.</span>
        </div>
      )}

      {data && data.scores.length > 0 && (
        <>
          {/* Summary row */}
          <div style={{ display: 'flex', gap: 16, marginBottom: 24, flexWrap: 'wrap' }}>
            {[
              ['Students Tracked', data.student_count, 'color-accent'],
              ['Avg Attention', `${(data.scores.reduce((s, r) => s + r.attention_avg, 0) / data.scores.length).toFixed(1)}%`, 'color-green'],
              ['Avg Final Score', `${(data.scores.reduce((s, r) => s + r.final_multimodal_score, 0) / data.scores.length).toFixed(1)}%`, 'color-accent'],
              ['Present', data.scores.filter(r => r.attendance_status !== 'Absent').length, 'color-green'],
              ['Absent', data.scores.filter(r => r.attendance_status === 'Absent').length, 'color-red'],
            ].map(([label, val, cls]) => (
              <div key={String(label)} className="stat-card" style={{ flex: '1 1 140px' }}>
                <div className="stat-label">{label}</div>
                <div className={`stat-value ${cls}`} style={{ fontSize: 28 }}>{val}</div>
              </div>
            ))}
          </div>

          {/* Bar Chart */}
          <div style={{ ...cardStyle, height: 360 }}>
            <h3 style={{ margin: '0 0 16px', fontSize: 15, color: 'var(--text)' }}>Performance Overview</h3>
            <ResponsiveContainer width="100%" height="85%">
              <BarChart data={data.scores} margin={{ top: 0, right: 10, left: 0, bottom: 40 }}>
                <XAxis
                  dataKey="name"
                  stroke="var(--text-dim)"
                  fontSize={11}
                  angle={-35}
                  textAnchor="end"
                  interval={0}
                />
                <YAxis stroke="var(--text-dim)" fontSize={11} domain={[0, 100]} />
                <Tooltip
                  contentStyle={{ backgroundColor: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 8 }}
                  labelStyle={{ color: 'var(--text)', fontWeight: 600 }}
                  formatter={(v) => `${Number(v).toFixed(1)}%`}
                />
                <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
                <Bar dataKey="attention_avg"          name="Attention (A_avg)" fill="#6366f1" radius={[4, 4, 0, 0]} />
                <Bar dataKey="final_multimodal_score" name="Final Score"       fill="#10b981" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Detailed scorecard */}
          <div style={cardStyle}>
            <h3 style={{ margin: '0 0 4px', fontSize: 15, color: 'var(--text)' }}>Detailed Scorecard</h3>
            <p style={{ margin: '0 0 16px', fontSize: 12, color: 'var(--text-dim)' }}>
              Final = 20% Punctuality + 70% Attention + 10% Q&A &nbsp;|&nbsp; Click column header to sort
            </p>
            <ScoreTable scores={data.scores} />
          </div>

          <h3 className="section-title" style={{marginTop: 32}}>Q&A Transcript Log</h3>
          <QATranscriptLog sessionId={selectedSessionId} />
        </>
      )}
    </div>
  )
}
