// src/components/AttentionChart.tsx
import { LineChart, Line, YAxis, ResponsiveContainer, ReferenceLine } from 'recharts'

interface Props {
  history: { time: string; attention: number }[]
}

export function AttentionChart({ history }: Props) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={history}>
        <YAxis domain={[0, 100]} hide />
        <ReferenceLine y={50} stroke="#FC6C54" strokeDasharray="3 3" opacity={0.3} />
        <Line 
          type="monotone" 
          dataKey="attention" 
          stroke="#1A3C61" 
          strokeWidth={2}
          dot={false}
          isAnimationActive={false} 
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
