// src/components/SessionSetup.tsx
import { useState } from 'react'

interface Props {
  onStart: (sub: string, st: string, en: string, t: string, d: string, r: string) => void
  loading: boolean
  initialTeacher: string
}

export function SessionSetup({ onStart, loading, initialTeacher }: Props) {
  const [subject, setSubject] = useState('')
  const [room, setRoom]       = useState('')
  const [div, setDiv]         = useState('A')
  const [dur, setDur]         = useState(60)
  const teacher = initialTeacher

  return (
    <div className="fixed inset-0 bg-blue/80 backdrop-blur-sm flex items-center justify-center z-[1000] p-4">
      <div className="bg-ivory border border-blue w-full max-w-md relative shadow-2xl">
        <div className="absolute top-0 left-0 w-full h-1 bg-coral" />
        <div className="p-6 border-b border-blue/20 bg-blue/5">
          <h2 className="text-lg font-black text-blue uppercase tracking-widest">New Session</h2>
        </div>
        
        <form className="p-6 flex flex-col gap-5" onSubmit={e => {
          e.preventDefault()
          const start = new Date()
          const end = new Date(start.getTime() + dur * 60000)
          onStart(subject, start.toISOString(), end.toISOString(), teacher, div, room)
        }}>
          
          <div className="flex flex-col gap-1.5">
            <label className="text-[10px] tracking-widest uppercase font-bold text-blue/60">Subject</label>
            <input required autoFocus value={subject} onChange={e=>setSubject(e.target.value)} 
                   className="bg-transparent border-b border-blue/40 text-blue font-bold text-sm py-1 outline-none focus:border-coral" 
                   placeholder="e.g. Physics 101" />
          </div>

          <div className="grid grid-cols-2 gap-6">
            <div className="flex flex-col gap-1.5">
              <label className="text-[10px] tracking-widest uppercase font-bold text-blue/60">Room</label>
              <input required value={room} onChange={e=>setRoom(e.target.value)} 
                     className="bg-transparent border-b border-blue/40 text-blue font-bold text-sm py-1 outline-none focus:border-coral" 
                     placeholder="e.g. 402" />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-[10px] tracking-widest uppercase font-bold text-blue/60">Division</label>
              <select value={div} onChange={e=>setDiv(e.target.value)} 
                      className="bg-transparent border-b border-blue/40 text-blue font-bold text-sm py-1 outline-none focus:border-coral">
                {['A','B','C','D'].map(d => <option key={d} value={d}>Div {d}</option>)}
              </select>
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-[10px] tracking-widest uppercase font-bold text-blue/60">Duration ({dur} mins)</label>
            <input type="range" min={15} max={180} step={15} value={dur} onChange={e=>setDur(parseInt(e.target.value))}
                   className="accent-coral" />
          </div>

          <button type="submit" disabled={loading || !subject || !room}
                  className="mt-4 bg-blue text-ivory text-xs tracking-[0.2em] uppercase font-bold py-4 hover:bg-coral transition-colors disabled:opacity-50">
            {loading ? 'Starting...' : 'Commence 🚀'}
          </button>
        </form>
      </div>
    </div>
  )
}
