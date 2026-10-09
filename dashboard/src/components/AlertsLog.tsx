// src/components/AlertsLog.tsx
interface Props {
  alerts: string[]
  onClear?: () => void
}

export function AlertsLog({ alerts }: Props) {
  if (alerts.length === 0) {
    return (
      <div className="h-full flex items-center justify-center text-[10px] tracking-widest uppercase font-bold text-blue/30">
        No Alerts
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-1.5 h-full overflow-y-auto pr-1 pb-2">
      {alerts.map((msg, i) => {
        const isCrit = msg.toLowerCase().includes('critical') || msg.toLowerCase().includes('multiple')
        return (
          <div key={i} className={`p-2 border-l-2 text-xs font-semibold ${
            isCrit ? 'border-coral bg-coral/10 text-coral' : 'border-blue/40 bg-blue/5 text-blue/80'
          }`}>
            {msg}
          </div>
        )
      })}
    </div>
  )
}
