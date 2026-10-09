import { useEffect, useState } from 'react'

interface QAInteraction {
  interaction_id: string
  roll_no: number
  question_text: string | null
  student_response_text: string | null
  llm_feedback: string | null
  qa_score: number
  student_responded: boolean
  teacher_interrupted: boolean
}

export function QATranscriptLog({ sessionId }: { sessionId: string }) {
  const [logs, setLogs] = useState<QAInteraction[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!sessionId) return
    setLoading(true)
    const token = localStorage.getItem('token')
    fetch(`/api/sessions/${sessionId}/qa`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then(r => r.json())
      .then(d => { setLogs(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [sessionId])

  if (loading) {
    return <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-muted)' }}>Loading Q&A logs...</div>
  }

  if (logs.length === 0) {
    return (
      <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)', background: 'var(--card-bg)', borderRadius: 12, border: '1px solid var(--border)' }}>
        No Q&A interactions recorded for this session.
      </div>
    )
  }

  return (
    <div style={{ background: 'var(--card-bg)', border: '1px solid var(--border)', borderRadius: 12, padding: 20 }}>
      <h4 style={{ margin: '0 0 16px', fontSize: 16 }}>Q&A Transcript Log</h4>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
        {logs.map((log, i) => (
          <div key={log.interaction_id}>
            <div style={{ display: 'flex', gap: 12, marginBottom: 8 }}>
              <div style={{
                background: 'rgba(59,130,246,0.1)', color: '#3b82f6',
                padding: '12px 16px', borderRadius: '12px 12px 12px 0',
                maxWidth: '80%'
              }}>
                <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 4 }}>🎓 Teacher → Roll {log.roll_no}</div>
                <div style={{ fontSize: 14 }}>"{log.question_text || '[Question not transcribed]'}"</div>
              </div>
            </div>

            <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end', marginBottom: 8 }}>
              <div style={{
                background: 'var(--surface)', color: 'var(--text)',
                border: '1px solid var(--border)',
                padding: '12px 16px', borderRadius: '12px 12px 0 12px',
                maxWidth: '80%'
              }}>
                {log.student_responded ? (
                  <>
                    <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 4 }}>👤 Roll {log.roll_no} Responded</div>
                    <div style={{ fontSize: 14 }}>"{log.student_response_text || '[Response not transcribed]'}"</div>
                  </>
                ) : log.teacher_interrupted ? (
                  <div style={{ fontSize: 14, fontStyle: 'italic', color: 'var(--text-muted)' }}>
                    🛑 Teacher interrupted — Q_i = 1.0 (safeguard)
                  </div>
                ) : (
                  <div style={{ fontSize: 14, fontStyle: 'italic', color: 'var(--text-muted)' }}>
                    ⏱️ No response — student timed out (Q_i = 0.0)
                  </div>
                )}
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'center' }}>
              <div style={{
                background: log.qa_score >= 0.8 ? 'rgba(16,185,129,0.1)' : log.qa_score >= 0.5 ? 'rgba(245,158,11,0.1)' : 'rgba(239,68,68,0.1)',
                border: `1px solid ${log.qa_score >= 0.8 ? 'var(--green)' : log.qa_score >= 0.5 ? '#f59e0b' : 'var(--red)'}`,
                color: log.qa_score >= 0.8 ? 'var(--green)' : log.qa_score >= 0.5 ? '#f59e0b' : 'var(--red)',
                padding: '8px 12px', borderRadius: 8, fontSize: 13,
                maxWidth: '90%', textAlign: 'center'
              }}>
                <div style={{ fontWeight: 600, marginBottom: 2 }}>
                  🤖 AI Grade: {log.qa_score.toFixed(2)} &nbsp;
                  {log.qa_score >= 0.8 ? '✅ Good answer' : log.qa_score >= 0.5 ? '⚠️ Needs improvement' : '❌ Poor / No answer'}
                </div>
                {log.llm_feedback && <div style={{ fontSize: 12 }}>"{log.llm_feedback}"</div>}
              </div>
            </div>
            {i < logs.length - 1 && <hr style={{ border: 'none', borderTop: '1px dashed var(--border)', margin: '24px 0 0 0' }} />}
          </div>
        ))}
      </div>
    </div>
  )
}
