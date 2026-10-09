// src/components/AttendanceLiveList.tsx
import { useState, useEffect } from 'react'

interface Props {
  sessionId: string
  telemetry: any
}

export function AttendanceLiveList({ sessionId, telemetry }: Props) {
  const [tab, setTab] = useState<'present'|'absent'>('absent')
  const [present, setPresent] = useState<number[]>([])
  const [absent, setAbsent] = useState<number[]>([])

  useEffect(() => {
    if (!sessionId) return
    const token = localStorage.getItem('token')
    fetch(`/api/sessions/${sessionId}/attendance`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {}
    }).then(r => r.json()).then(data => {
      setPresent(data.present ?? [])
      setAbsent(data.absent ?? [])
    }).catch(() => {})
  }, [sessionId, telemetry?.timestamp]) // Refresh when telemetry ticks

  return (
    <div className="flex flex-col h-full bg-ivory border border-blue/20">
      <div className="flex border-b border-blue/20">
        <button onClick={() => setTab('absent')} className={`flex-1 py-2 text-[9px] tracking-widest uppercase font-bold ${tab === 'absent' ? 'bg-coral text-ivory' : 'bg-blue/5 text-blue hover:bg-blue/10'}`}>
          Absent ({absent.length})
        </button>
        <button onClick={() => setTab('present')} className={`flex-1 py-2 text-[9px] tracking-widest uppercase font-bold ${tab === 'present' ? 'bg-blue text-ivory' : 'bg-blue/5 text-blue hover:bg-blue/10'}`}>
          Present ({present.length})
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-3">
        <div className="flex flex-wrap gap-2">
          {(tab === 'absent' ? absent : present).map((roll: number) => (
            <span key={roll} className={`px-2 py-1 text-[9px] font-black border ${
              tab === 'absent' ? 'border-coral text-coral bg-coral/5' : 'border-blue text-blue bg-blue/5'
            }`}>
              R{roll}
            </span>
          ))}
          {(tab === 'absent' ? absent : present).length === 0 && (
            <span className="text-[9px] tracking-widest uppercase text-blue/30 font-bold p-2">None</span>
          )}
        </div>
      </div>
    </div>
  )
}
