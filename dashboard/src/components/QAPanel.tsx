// src/components/QAPanel.tsx
import type { QAWindowStatus } from '../types'

interface Props {
  qa: QAWindowStatus
}

export function QAPanel({ qa }: Props) {
  if (!qa.active) {
    return (
      <div className="qa-panel">
        <div className="qa-title">Q&amp;A Monitor</div>
        <div className="qa-idle">-- Waiting for teacher to address a student --</div>
      </div>
    )
  }

  const secs    = Math.ceil(qa.seconds_remaining)
  const urgent  = secs <= 5
  const wrong   = qa.wrong_student && qa.speaker_roll != null

  return (
    <div className={`qa-panel ${wrong ? 'wrong' : 'active'}`}>
      <div className="qa-title">Q&amp;A Window</div>

      <div className="qa-roll">Roll {qa.asked_roll} asked</div>
      {qa.question_text && (
        <div className="qa-question">"{qa.question_text}"</div>
      )}

      <div className={`qa-countdown ${urgent ? 'urgent' : 'ok'}`}>
        {secs}s
      </div>

      {qa.speaker_roll != null && (
        <div className={`qa-speaker ${wrong ? 'wrong' : 'correct'}`}>
          {wrong
            ? `⚠️  Roll ${qa.speaker_roll} answering instead of Roll ${qa.asked_roll}!`
            : `✓ Roll ${qa.speaker_roll} is responding`
          }
        </div>
      )}
    </div>
  )
}
