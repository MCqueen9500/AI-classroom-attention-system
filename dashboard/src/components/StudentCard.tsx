// src/components/StudentCard.tsx
import type { FaceData } from '../types'

interface Props {
  face: FaceData
  isWrongSpeaker: boolean
  onClick: () => void
}

function scoreColor(v: number): string {
  if (v >= 0.75) return 'var(--green)'
  if (v >= 0.50) return 'var(--yellow)'
  return 'var(--red)'
}

function cardClass(face: FaceData, wrong: boolean): string {
  if (wrong) return 'student-card wrong-speaker'
  if (face.is_speaking) return 'student-card speaking'
  if (face.a_i >= 0.75) return 'student-card attentive'
  if (face.a_i >= 0.50) return 'student-card partial'
  return 'student-card distracted'
}

function ScoreBar({ label, value }: { label: string; value: number }) {
  return (
    <div className="score-bar-row">
      <span className="score-bar-label">{label}</span>
      <div className="score-bar-track">
        <div
          className="score-bar-fill"
          style={{ width: `${Math.round(value * 100)}%`, background: scoreColor(value) }}
        />
      </div>
    </div>
  )
}

export function StudentCard({ face, isWrongSpeaker, onClick }: Props) {
  const pct = Math.round(face.a_i * 100)
  return (
    <div className={cardClass(face, isWrongSpeaker)} onClick={onClick} title={`Roll ${face.roll_no}`}>
      <div className="student-roll">Roll {face.roll_no}</div>
      <div className="student-score" style={{ color: scoreColor(face.a_i) }}>
        {pct}<span style={{ fontSize: 12 }}>%</span>
      </div>
      <div className="score-bars">
        <ScoreBar label="H" value={face.h_i} />
        <ScoreBar label="G" value={face.g_i} />
        <ScoreBar label="P" value={face.p_i} />
      </div>
      <div className="student-badges">
        {face.is_drowsy   && <span className="badge badge-drowsy">Drowsy</span>}
        {face.is_speaking && !isWrongSpeaker && <span className="badge badge-speaking">Speaking</span>}
        {isWrongSpeaker   && <span className="badge badge-wrong">Wrong!</span>}
      </div>
    </div>
  )
}
