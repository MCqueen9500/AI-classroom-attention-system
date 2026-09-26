// src/components/AlertsLog.tsx
interface Props {
  alerts: string[]
  onClear: () => void
}

function alertClass(msg: string): string {
  const m = msg.toLowerCase()
  if (m.includes('wrong') || m.includes('wrong_student')) return 'alert-item wrong'
  if (m.includes('drowsy') || m.includes('sleep'))        return 'alert-item drowsy'
  return 'alert-item info'
}

export function AlertsLog({ alerts, onClear }: Props) {
  return (
    <div>
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom: 8 }}>
        <div className="section-title">Live Alerts</div>
        {alerts.length > 0 && (
          <button
            className="btn btn-primary"
            style={{ padding: '3px 10px', fontSize: 11 }}
            onClick={onClear}
          >
            Clear
          </button>
        )}
      </div>
      <div className="alerts-panel">
        {alerts.length === 0 && <div className="no-alerts">No alerts</div>}
        {[...alerts].reverse().slice(0, 15).map((a, i) => (
          <div key={i} className={alertClass(a)}>{a}</div>
        ))}
      </div>
    </div>
  )
}
