// src/components/StudentCard.tsx
import { type FaceData } from '../types'

interface Props {
  face: FaceData
  isWrongSpeaker?: boolean
  onClick?: () => void
}

export function StudentCard({ face, isWrongSpeaker, onClick }: Props) {
  // a_i is 0.0 to 1.0 (or 0-100)
  const score = face.a_i > 1 ? face.a_i : face.a_i * 100
  const isAttentive = score >= 50
  
  let statusText = 'Attentive'
  if (face.is_drowsy) statusText = 'Drowsy'
  else if (face.is_speaking) statusText = 'Speaking'
  else if (!isAttentive) statusText = 'Distracted'

  return (
    <div 
      onClick={onClick}
      className={`border p-2 cursor-pointer transition-all ${
        isWrongSpeaker ? 'border-coral bg-coral/5 animate-pulse' :
        !isAttentive   ? 'border-yellow-600/50 bg-yellow-600/5' :
        'border-blue/20 bg-ivory hover:border-blue'
      }`}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] tracking-widest font-black text-blue">
          {face.roll_no ? `R${face.roll_no}` : '?'}
        </span>
        <span className={`text-[9px] tracking-widest uppercase font-bold ${
          isAttentive ? 'text-green-600' : 'text-coral'
        }`}>
          {Math.round(score)}%
        </span>
      </div>
      <div className="text-[8px] tracking-widest uppercase font-bold text-blue/50 truncate">
        {statusText}
      </div>
    </div>
  )
}
