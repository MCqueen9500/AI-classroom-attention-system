// src/components/SessionSetup.tsx
// Modal shown when no active session exists

import { useState } from 'react'

interface Props {
  onStart: (subject: string, start: string, end: string) => void
  loading: boolean
}

function now()    { return new Date().toISOString().slice(0, 16) }
function inHour() { return new Date(Date.now() + 3600000).toISOString().slice(0, 16) }

export function SessionSetup({ onStart, loading }: Props) {
  const [subject, setSubject] = useState('Computer Vision Lab')
  const [start,   setStart]   = useState(now())
  const [end,     setEnd]     = useState(inHour())

  return (
    <div className="modal-overlay">
      <div className="modal">
        <h2>Start New Session</h2>
        <p style={{ fontSize: 13, color: 'var(--text-dim)' }}>
          Configure the monitoring session to begin tracking student attention.
        </p>

        <label>
          Subject / Topic
          <input value={subject} onChange={e => setSubject(e.target.value)} placeholder="e.g. Computer Vision" />
        </label>

        <label>
          Scheduled Start
          <input type="datetime-local" value={start} onChange={e => setStart(e.target.value)} />
        </label>

        <label>
          Scheduled End
          <input type="datetime-local" value={end} onChange={e => setEnd(e.target.value)} />
        </label>

        <button
          className="btn btn-primary"
          style={{ padding: '10px', fontSize: 15, marginTop: 4 }}
          disabled={loading || !subject.trim()}
          onClick={() => onStart(subject, start + ':00', end + ':00')}
        >
          {loading ? 'Creating...' : 'Start Session'}
        </button>
      </div>
    </div>
  )
}
