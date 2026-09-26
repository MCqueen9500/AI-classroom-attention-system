// src/components/AttentionChart.tsx
// Line chart showing class attention % over time using Recharts

import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts'

interface DataPoint {
  time: string
  attention: number
}

interface Props {
  history: DataPoint[]
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch {
    return iso
  }
}

export function AttentionChart({ history }: Props) {
  if (history.length < 2) {
    return (
      <div className="chart-wrap" style={{ textAlign:'center', color:'var(--text-dim)', padding: 32 }}>
        Collecting data... (need at least 2 points)
      </div>
    )
  }

  const data = history.map(p => ({
    time:      formatTime(p.time),
    attention: Math.round(p.attention),
  }))

  return (
    <div className="chart-wrap">
      <div className="section-title" style={{ marginBottom: 14 }}>Class Attention Over Time</div>
      <ResponsiveContainer width="100%" height={180}>
        <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis
            dataKey="time"
            tick={{ fontSize: 10, fill: 'var(--text-dim)' }}
            tickLine={false}
            interval="preserveStartEnd"
          />
          <YAxis
            domain={[0, 100]}
            tick={{ fontSize: 10, fill: 'var(--text-dim)' }}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip
            contentStyle={{ background:'var(--surface2)', border:'1px solid var(--border)', borderRadius: 8 }}
            labelStyle={{ color:'var(--text-dim)' }}
            itemStyle={{ color:'var(--accent)' }}
            formatter={(v) => [`${Number(v ?? 0)}%`, 'Attention']}
          />
          <ReferenceLine y={75} stroke="var(--green)"  strokeDasharray="4 4" />
          <ReferenceLine y={50} stroke="var(--yellow)" strokeDasharray="4 4" />
          <Line
            type="monotone"
            dataKey="attention"
            stroke="var(--accent)"
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
      <div style={{ display:'flex', gap:16, fontSize:10, color:'var(--text-dim)', marginTop: 8 }}>
        <span style={{ color:'var(--green)' }}>— 75% threshold</span>
        <span style={{ color:'var(--yellow)' }}>— 50% threshold</span>
      </div>
    </div>
  )
}
