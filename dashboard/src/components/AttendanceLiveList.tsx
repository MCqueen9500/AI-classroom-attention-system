import { useEffect, useState } from 'react'
import { useApi } from '../hooks/useApi'

interface AttendanceRecord {
  roll_no: number
  name: string
  status: string
  punctuality_score: number
}

export function AttendanceLiveList({ sessionId, telemetry }: { sessionId: string, telemetry: any }) {
  const [list, setList] = useState<AttendanceRecord[]>([])
  const { getSessionAttendance } = useApi()

  const fetchAttendance = () => {
    getSessionAttendance(sessionId).then((res: any) => {
      if (res) {
        setList([...res].sort((a, b) => {
          if (a.status === 'Present' && b.status !== 'Present') return -1
          if (a.status !== 'Present' && b.status === 'Present') return 1
          return a.roll_no - b.roll_no
        }))
      }
    })
  }

  useEffect(() => {
    fetchAttendance()
  }, [sessionId]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (telemetry?.alerts) {
      if (telemetry.alerts.some((a: any) => a.message.includes('marked PRESENT'))) {
        fetchAttendance()
      }
    }
  }, [telemetry?.alerts]) // eslint-disable-line react-hooks/exhaustive-deps

  const presentCount = list.filter(r => r.status === 'Present').length

  return (
    <div style={{ background: 'var(--card-bg)', border: '1px solid var(--border)', borderRadius: 12, padding: '16px 0', marginTop: 24 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0 16px', marginBottom: 12 }}>
        <h4 style={{ margin: 0, fontSize: 14 }}>Attendance (Live)</h4>
        <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>[{presentCount} Present / {list.length} Total]</div>
      </div>
      <div style={{ maxHeight: 300, overflowY: 'auto', padding: '0 16px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {list.map(r => (
            <div key={r.roll_no} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 12px', background: 'var(--surface)', borderRadius: 6, border: '1px solid var(--border)', fontSize: 13 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <span style={{ color: r.status === 'Present' ? 'var(--green)' : 'var(--red)', fontSize: 10 }}>{r.status === 'Present' ? '🟢' : '🔴'}</span>
                <span style={{ fontWeight: 600, width: 60 }}>Roll {r.roll_no}</span>
                <span style={{ color: 'var(--text)' }}>{r.name}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                <span style={{ color: r.status === 'Present' ? 'var(--green)' : 'var(--text-muted)' }}>{r.status}</span>
                {r.status === 'Present' && <span style={{ fontWeight: 600 }}>{(r.punctuality_score * 100).toFixed(1)}%</span>}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
