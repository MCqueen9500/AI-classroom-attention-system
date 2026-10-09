// src/components/QAPanel.tsx
import { type QAWindowStatus } from '../types'

interface Props {
  qa?: QAWindowStatus
}

export function QAPanel({ qa }: Props) {
  const isActive = qa?.active
  
  return (
    <div className="bg-ivory border border-blue/20 flex flex-col h-full min-h-[400px]">
      <div className="border-b border-blue/20 p-3 bg-blue/5 flex items-center justify-between">
        <h3 className="text-xs tracking-widest uppercase font-bold text-blue">Q&A Monitor</h3>
        <div className="flex items-center gap-2">
           <div className={`w-1.5 h-1.5 rounded-full ${isActive ? 'bg-coral animate-pulse' : 'bg-blue/30'}`} />
           <span className="text-[9px] tracking-widest uppercase font-bold text-blue/50">
             {isActive ? 'Listening' : 'Standby'}
           </span>
        </div>
      </div>
      
      <div className="flex-1 p-5 flex flex-col items-center justify-center text-center">
        {!isActive ? (
          <p className="text-xs tracking-widest uppercase font-bold text-blue/30 leading-loose">
            Waiting for<br/>Teacher Query
          </p>
        ) : (
          <div className="w-full flex flex-col items-center animate-in fade-in zoom-in duration-300">
            <div className="w-16 h-16 rounded-full border border-blue flex items-center justify-center text-xl font-black text-blue mb-4 shadow-sm bg-ivory">
              {qa.asked_roll}
            </div>
            <div className="text-[9px] tracking-widest uppercase font-bold text-blue/50 mb-1">Target Roll</div>
            
            {qa.wrong_student && (
              <div className="mt-8 border border-coral bg-coral/5 p-4 w-full">
                <div className="text-xs tracking-widest uppercase font-bold text-coral mb-2">Interruption</div>
                <div className="text-sm font-bold text-blue">Roll {qa.speaker_roll} answered instead</div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
