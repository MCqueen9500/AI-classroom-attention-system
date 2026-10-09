// src/pages/Dashboard.tsx
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
  if (pct >= 75) return 'text-green-600'
  if (pct >= 50) return 'text-yellow-600'
  return 'text-coral'
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

  useEffect(() => {
    api.getActiveSesion().then(s => { if (s) setSession(s) })
  }, [])

  const { telemetry, status, alerts, clearAlerts } = useWebSocket(session?.session_id ?? '')
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
    if (s) { setSession(s); setShowSetup(false); }
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

  // ── IDLE STATE ────────────────────────────────────────────────────────
  if (!session) {
    return (
      <>
        {showSetup && (
          <SessionSetup onStart={handleCreateSession} loading={api.loading} initialTeacher={user?.name ?? ''} />
        )}
        <div className="flex items-center justify-center h-full p-10">
          <div className="bg-ivory border border-blue/20 p-16 text-center max-w-lg w-full relative">
            <div className="absolute top-0 left-0 w-full h-1 bg-blue" />
            
            <div className="text-4xl mb-6 text-blue opacity-50">📋</div>
            <h2 className="text-2xl font-black text-blue tracking-tight mb-2 uppercase">No Active Session</h2>
            
            <p className="text-blue/60 text-sm mb-10 leading-relaxed font-medium">
              {user?.name ? `Welcome, ${user.name}. ` : ''} 
              Start a new session to begin monitoring student attention in real time.
            </p>
            
            <button
              onClick={() => setShowSetup(true)}
              className="bg-blue text-ivory text-xs tracking-[0.2em] uppercase font-bold py-4 px-8 w-full transition-colors hover:bg-coral"
            >
              + Start New Session
            </button>

            {api.error && (
              <div className="mt-6 border border-coral text-coral bg-coral/5 text-xs px-4 py-3 font-semibold">
                {api.error}
              </div>
            )}
          </div>
        </div>
      </>
    )
  }

  // ── ACTIVE SESSION ────────────────────────────────────────────────────
  return (
    <div className="flex h-full font-sans">
      {collectiveAlert && <CollectiveAlert onDismiss={handleResume} />}
      {selectedRoll !== null && <StudentModal rollNo={selectedRoll} onClose={() => setSelectedRoll(null)} />}
      
      {/* End Session Confirm */}
      {confirmEnd && (
        <div className="fixed inset-0 bg-blue/80 backdrop-blur-sm flex items-center justify-center z-[1000]">
          <div className="bg-ivory border border-blue p-10 text-center max-w-sm w-full shadow-2xl relative">
            <div className="absolute top-0 left-0 w-full h-1 bg-coral" />
            <div className="text-4xl mb-4">⚠️</div>
            <h3 className="text-xl font-black text-blue uppercase tracking-tight mb-3">End Session?</h3>
            <p className="text-blue/70 text-sm mb-8 font-medium">
              This stops monitoring and finalizes data.
            </p>
            <div className="flex gap-4">
              <button onClick={() => setConfirmEnd(false)} className="flex-1 py-3 text-xs tracking-widest uppercase font-bold text-blue border border-blue hover:bg-blue/5">
                Cancel
              </button>
              <button onClick={handleEndSession} className="flex-1 py-3 text-xs tracking-widest uppercase font-bold text-ivory bg-coral hover:bg-red-600 transition-colors">
                End It
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Main UI */}
      <div className="flex-1 px-4 lg:px-8 py-2 overflow-y-auto">
        
        {/* Top Banner */}
        <div className="bg-ivory border border-blue/20 p-5 mb-8 flex items-center justify-between flex-wrap gap-6 relative shadow-sm">
          <div className="absolute left-0 top-0 bottom-0 w-1 bg-blue" />
          
          <div className="flex items-center gap-8 pl-2">
            <div>
              <div className="text-[9px] text-blue/50 uppercase tracking-widest mb-1 font-bold">Subject</div>
              <div className="font-black text-blue text-lg uppercase tracking-tight">{session.subject_name}</div>
            </div>
            <div className="hidden sm:block">
              <div className="text-[9px] text-blue/50 uppercase tracking-widest mb-1 font-bold">Teacher</div>
              <div className="font-bold text-blue text-sm">{session.teacher_name}</div>
            </div>
            <div>
              <div className="text-[9px] text-blue/50 uppercase tracking-widest mb-1 font-bold">Div & Room</div>
              <div className="font-bold text-blue text-sm">Div {session.class_div} · {session.room_no}</div>
            </div>
            <div className="hidden md:block">
              <div className="text-[9px] text-blue/50 uppercase tracking-widest mb-1 font-bold">Time</div>
              <div className="font-bold text-blue text-sm opacity-80">
                {new Date(session.scheduled_start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                {' → '}
                {new Date(session.scheduled_end).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <div className="text-[10px] tracking-widest uppercase font-bold px-3 py-1 border border-blue/20 text-blue/70 bg-blue/5">
              {status}
            </div>
            
            {isPaused 
              ? <button onClick={handleResume} className="text-xs tracking-widest uppercase font-bold px-5 py-2.5 bg-blue text-ivory hover:bg-coral transition-colors">Resume ▶</button>
              : <button onClick={handlePause}  className="text-xs tracking-widest uppercase font-bold px-5 py-2.5 border border-blue text-blue hover:bg-blue/5 transition-colors">Pause ⏸</button>
            }
            <button onClick={() => setConfirmEnd(true)} className="text-xs tracking-widest uppercase font-bold px-5 py-2.5 bg-coral text-ivory hover:bg-red-600 transition-colors">
              End ⏹
            </button>
          </div>
        </div>

        {/* 3-Column Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          
          {/* Col 1: Chart & Alerts */}
          <div className="lg:col-span-3 flex flex-col gap-6">
            <div className="bg-ivory border border-blue/20 flex flex-col min-h-[300px]">
              <div className="border-b border-blue/20 p-3 bg-blue/5">
                <h3 className="text-xs tracking-widest uppercase font-bold text-blue">Class Attention</h3>
              </div>
              <div className="flex-1 p-4 flex flex-col">
                <div className="flex items-baseline gap-2 mb-2">
                  <span className={`text-4xl font-black ${attentionColor(classPct)}`}>
                    {classPct.toFixed(0)}%
                  </span>
                  <span className="text-xs tracking-widest uppercase font-bold text-blue/40">Current</span>
                </div>
                <div className="flex-1 mt-2">
                  <AttentionChart history={history} />
                </div>
              </div>
            </div>

            <div className="bg-ivory border border-blue/20 flex flex-col h-64">
              <div className="border-b border-blue/20 p-3 bg-blue/5 flex justify-between items-center">
                <h3 className="text-xs tracking-widest uppercase font-bold text-blue">Alerts Log</h3>
                <button onClick={clearAlerts} className="text-[9px] tracking-widest uppercase text-blue/50 hover:text-coral font-bold">Clear</button>
              </div>
              <div className="flex-1 overflow-hidden p-2">
                <AlertsLog alerts={alerts} onClear={clearAlerts} />
              </div>
            </div>
            
            <div className="bg-ivory border border-blue/20 flex flex-col h-64">
               <AttendanceLiveList sessionId={session.session_id} telemetry={telemetry} />
            </div>
          </div>

          {/* Col 2: Face Grid */}
          <div className="lg:col-span-6 bg-ivory border border-blue/20 flex flex-col">
            <div className="border-b border-blue/20 p-3 bg-blue/5 flex justify-between items-center">
              <h3 className="text-xs tracking-widest uppercase font-bold text-blue">Live Camera Feed</h3>
              <span className="text-[10px] tracking-widest uppercase text-blue/60 font-bold bg-blue/10 px-2 py-0.5">
                {faces.length} Detected
              </span>
            </div>
            <div className="flex-1 bg-ivory/50 p-4">
              <div className="grid grid-cols-3 gap-3">
                {faces.map((f, i) => (
                  <StudentCard 
                    key={i} 
                    face={f} 
                    isWrongSpeaker={f.roll_no === wrongRoll} 
                    onClick={() => f.roll_no && setSelectedRoll(f.roll_no)}
                  />
                ))}
                {faces.length === 0 && (
                  <div className="col-span-3 text-center py-16 text-sm tracking-widest uppercase text-blue/40 font-bold">
                    No faces detected in frame
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Col 3: Q&A */}
          <div className="lg:col-span-3">
            <QAPanel qa={qa} />
          </div>

        </div>
      </div>
    </div>
  )
}
