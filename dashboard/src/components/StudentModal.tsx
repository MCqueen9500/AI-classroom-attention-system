import React, { useEffect, useState } from 'react'

interface HistoryRecord {
  session_id: string
  subject_name: string
  scheduled_start: string
  attendance_status: string
  punctuality_score: number
  attention_avg: number
  qa_score: number
  final_multimodal_score: number
}

interface StudentHistory {
  roll_no: number
  name: string
  class_div: string
  history: HistoryRecord[]
}

interface Props {
  rollNo: number
  onClose: () => void
}

export function StudentModal({ rollNo, onClose }: Props) {
  const [data, setData] = useState<StudentHistory | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('token')
    fetch(`/api/students/${rollNo}/history`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then(r => r.json())
      .then(d => {
        setData(d)
        setLoading(false)
      })
      .catch(console.error)
  }, [rollNo])

  return (
    <div className="modal-overlay" onClick={onClose} style={{
      position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
      background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000
    }}>
      <div className="modal-content" onClick={e => e.stopPropagation()} style={{
        background: 'var(--bg-card)', padding: 30, borderRadius: 12, width: '80%', maxWidth: 800, maxHeight: '80vh', overflowY: 'auto'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
          <h2 style={{ margin: 0 }}>Student Profile</h2>
          <button className="btn" onClick={onClose}>Close</button>
        </div>

        {loading && <div>Loading...</div>}

        {data && (
          <>
            <div style={{ display: 'flex', gap: 20, marginBottom: 30 }}>
              <div style={{ width: 80, height: 80, borderRadius: '50%', background: 'var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 24, fontWeight: 'bold' }}>
                {data.roll_no}
              </div>
              <div>
                <h1 style={{ margin: '0 0 8px 0' }}>{data.name}</h1>
                <div style={{ color: 'var(--text-dim)' }}>Class: {data.class_div}</div>
              </div>
            </div>

            <h3 style={{ borderBottom: '1px solid var(--border)', paddingBottom: 10 }}>Session History</h3>
            
            <table style={{ width: '100%', textAlign: 'left', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ color: 'var(--text-dim)', borderBottom: '1px solid var(--border)' }}>
                  <th style={{ padding: 10 }}>Date</th>
                  <th style={{ padding: 10 }}>Subject</th>
                  <th style={{ padding: 10 }}>Attendance</th>
                  <th style={{ padding: 10 }}>A_avg</th>
                  <th style={{ padding: 10 }}>Q_i</th>
                  <th style={{ padding: 10 }}>Final %</th>
                </tr>
              </thead>
              <tbody>
                {data.history.map(h => (
                  <tr key={h.session_id} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{ padding: 10 }}>{new Date(h.scheduled_start).toLocaleDateString()}</td>
                    <td style={{ padding: 10 }}>{h.subject_name}</td>
                    <td style={{ padding: 10 }}>
                      <span className={h.attendance_status === 'On-Time' ? 'color-green' : 'color-red'}>{h.attendance_status}</span>
                    </td>
                    <td style={{ padding: 10 }}>{h.attention_avg}%</td>
                    <td style={{ padding: 10 }}>{h.qa_score}%</td>
                    <td style={{ padding: 10, fontWeight: 'bold' }}>{h.final_multimodal_score}%</td>
                  </tr>
                ))}
                {data.history.length === 0 && (
                  <tr><td colSpan={6} style={{ padding: 20, textAlign: 'center', color: 'var(--text-dim)' }}>No sessions recorded</td></tr>
                )}
              </tbody>
            </table>
          </>
        )}
      </div>
    </div>
  )
}
