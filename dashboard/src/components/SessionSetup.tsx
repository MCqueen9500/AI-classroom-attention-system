// src/components/SessionSetup.tsx
// Full session creation form with all required fields

import { useState } from 'react'

interface Props {
  onStart: (
    subject: string,
    start: string,
    end: string,
    teacher: string,
    div: string,
    room: string,
  ) => void
  loading: boolean
  initialTeacher?: string
}

function nowLocal()   { return new Date(Date.now() - new Date().getTimezoneOffset()*60000).toISOString().slice(0, 16) }
function inHourLocal(){ return new Date(Date.now() - new Date().getTimezoneOffset()*60000 + 3600000).toISOString().slice(0, 16) }

const SUBJECTS = [
  'Computer Vision', 'Machine Learning', 'Data Structures',
  'Operating Systems', 'DBMS', 'Computer Networks',
  'Digital Electronics', 'Mathematics', 'Physics', 'Other',
]

const DIVISIONS = ['A', 'B', 'C', 'D', 'E', 'F']

export function SessionSetup({ onStart, loading, initialTeacher = '' }: Props) {
  const [subject,  setSubject]  = useState('Computer Vision')
  const [teacher,  setTeacher]  = useState(initialTeacher)
  const [div,      setDiv]      = useState('A')
  const [room,     setRoom]     = useState('Lab 1')
  const [start,    setStart]    = useState(nowLocal())
  const [end,      setEnd]      = useState(inHourLocal())

  const isValid = subject.trim() && teacher.trim() && div && room.trim()

  return (
    <div style={{
      position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
      background: 'rgba(0,0,0,0.75)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 999,
    }}>
      <div style={{
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        borderRadius: 16,
        padding: '36px 40px',
        width: 520,
        boxShadow: '0 20px 60px rgba(0,0,0,0.6)',
      }}>
        {/* Header */}
        <div style={{ marginBottom: 28 }}>
          <h2 style={{ margin: '0 0 6px 0', fontSize: 24, fontWeight: 700 }}>
            Start New Session
          </h2>
          <p style={{ color: 'var(--text-dim)', fontSize: 14, margin: 0 }}>
            Configure the class before monitoring begins.
          </p>
        </div>

        {/* Subject */}
        <div style={{ marginBottom: 18 }}>
          <label style={{ display: 'block', fontWeight: 600, marginBottom: 8, fontSize: 13 }}>
            Subject / Topic *
          </label>
          <div style={{ display: 'flex', gap: 8 }}>
            <select
              value={subject}
              onChange={e => setSubject(e.target.value)}
              style={{
                flex: 1, background: 'var(--surface2)', border: '1px solid var(--border)',
                borderRadius: 8, padding: '10px 12px', color: 'var(--text)', fontSize: 14,
              }}
            >
              {SUBJECTS.map(s => <option key={s}>{s}</option>)}
            </select>
            {subject === 'Other' && (
              <input
                placeholder="Enter subject name"
                onChange={e => setSubject(e.target.value)}
                style={{
                  flex: 1, background: 'var(--surface2)', border: '1px solid var(--border)',
                  borderRadius: 8, padding: '10px 12px', color: 'var(--text)', fontSize: 14,
                }}
              />
            )}
          </div>
        </div>

        {/* Teacher */}
        <div style={{ marginBottom: 18 }}>
          <label style={{ display: 'block', fontWeight: 600, marginBottom: 8, fontSize: 13 }}>
            Teacher Name *
          </label>
          <input
            value={teacher}
            onChange={e => setTeacher(e.target.value)}
            placeholder="e.g. Prof. Sharma"
            style={{
              width: '100%', background: 'var(--surface2)', border: '1px solid var(--border)',
              borderRadius: 8, padding: '10px 12px', color: 'var(--text)', fontSize: 14,
              boxSizing: 'border-box',
            }}
          />
        </div>

        {/* Division + Room */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 18 }}>
          <div>
            <label style={{ display: 'block', fontWeight: 600, marginBottom: 8, fontSize: 13 }}>
              Division *
            </label>
            <select
              value={div}
              onChange={e => setDiv(e.target.value)}
              style={{
                width: '100%', background: 'var(--surface2)', border: '1px solid var(--border)',
                borderRadius: 8, padding: '10px 12px', color: 'var(--text)', fontSize: 14,
              }}
            >
              {DIVISIONS.map(d => <option key={d}>Div {d}</option>)}
            </select>
          </div>
          <div>
            <label style={{ display: 'block', fontWeight: 600, marginBottom: 8, fontSize: 13 }}>
              Room / Lab *
            </label>
            <input
              value={room}
              onChange={e => setRoom(e.target.value)}
              placeholder="e.g. Lab 3, Room 201"
              style={{
                width: '100%', background: 'var(--surface2)', border: '1px solid var(--border)',
                borderRadius: 8, padding: '10px 12px', color: 'var(--text)', fontSize: 14,
                boxSizing: 'border-box',
              }}
            />
          </div>
        </div>

        {/* Time Range */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 28 }}>
          <div>
            <label style={{ display: 'block', fontWeight: 600, marginBottom: 8, fontSize: 13 }}>
              Start Time *
            </label>
            <input
              type="datetime-local"
              value={start}
              onChange={e => setStart(e.target.value)}
              style={{
                width: '100%', background: 'var(--surface2)', border: '1px solid var(--border)',
                borderRadius: 8, padding: '10px 12px', color: 'var(--text)', fontSize: 13,
                boxSizing: 'border-box',
              }}
            />
          </div>
          <div>
            <label style={{ display: 'block', fontWeight: 600, marginBottom: 8, fontSize: 13 }}>
              End Time *
            </label>
            <input
              type="datetime-local"
              value={end}
              onChange={e => setEnd(e.target.value)}
              style={{
                width: '100%', background: 'var(--surface2)', border: '1px solid var(--border)',
                borderRadius: 8, padding: '10px 12px', color: 'var(--text)', fontSize: 13,
                boxSizing: 'border-box',
              }}
            />
          </div>
        </div>

        {/* Summary preview */}
        {isValid && (
          <div style={{
            background: 'rgba(79, 142, 247, 0.08)',
            border: '1px solid rgba(79, 142, 247, 0.25)',
            borderRadius: 10, padding: '12px 16px', marginBottom: 20,
            fontSize: 13, color: 'var(--text-dim)', lineHeight: 1.8,
          }}>
            <strong style={{ color: 'var(--accent)' }}>Session Preview</strong><br />
            📚 {subject} &nbsp;|&nbsp; 👨‍🏫 {teacher} &nbsp;|&nbsp; 🏷️ Div {div} &nbsp;|&nbsp; 🏛️ {room}
          </div>
        )}

        <button
          style={{
            width: '100%', padding: '14px', fontSize: 16, fontWeight: 700,
            background: isValid ? 'var(--accent)' : 'var(--border)',
            color: '#fff', border: 'none', borderRadius: 10, cursor: isValid ? 'pointer' : 'not-allowed',
            transition: 'all 0.2s',
          }}
          disabled={loading || !isValid}
          onClick={() => onStart(subject, start + ':00', end + ':00', teacher, div.replace('Div ', ''), room)}
        >
          {loading ? 'Creating Session...' : '🚀 Start Monitoring'}
        </button>
      </div>
    </div>
  )
}
