import React, { useState } from 'react'

export interface ScoreRow {
  roll_no: number
  name: string
  attendance_status: string
  punctuality_score: number
  attention_avg: number
  qa_score: number
  final_multimodal_score: number
  requires_review: boolean
}

interface Props {
  scores: ScoreRow[]
}

export function ScoreTable({ scores }: Props) {
  const [sortCol, setSortCol] = useState<keyof ScoreRow>('final_multimodal_score')
  const [sortDesc, setSortDesc] = useState(true)

  const sorted = [...scores].sort((a, b) => {
    const va = a[sortCol]
    const vb = b[sortCol]
    if (va < vb) return sortDesc ? 1 : -1
    if (va > vb) return sortDesc ? -1 : 1
    return 0
  })

  function handleSort(col: keyof ScoreRow) {
    if (sortCol === col) setSortDesc(!sortDesc)
    else {
      setSortCol(col)
      setSortDesc(true)
    }
  }

  function renderTh(label: string, col: keyof ScoreRow) {
    return (
      <th onClick={() => handleSort(col)} style={{ cursor: 'pointer', userSelect: 'none' }}>
        {label} {sortCol === col ? (sortDesc ? '↓' : '↑') : ''}
      </th>
    )
  }

  return (
    <div style={{ overflowX: 'auto', marginTop: 20 }}>
      <table className="score-table" style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
        <thead>
          <tr style={{ borderBottom: '2px solid var(--border)' }}>
            {renderTh('Roll No', 'roll_no')}
            {renderTh('Name', 'name')}
            {renderTh('Attendance', 'punctuality_score')}
            {renderTh('Attention (A_avg)', 'attention_avg')}
            {renderTh('Q&A (Q_i)', 'qa_score')}
            {renderTh('Final %', 'final_multimodal_score')}
          </tr>
        </thead>
        <tbody>
          {sorted.map(s => (
            <tr key={s.roll_no} style={{ borderBottom: '1px solid var(--border)' }}>
              <td style={{ padding: '12px 8px' }}>{s.roll_no}</td>
              <td style={{ padding: '12px 8px', fontWeight: 500 }}>
                {s.name}
                {s.requires_review && <span title="Low Vision Confidence" style={{ color: 'var(--red)', marginLeft: 5 }}>⚠️</span>}
              </td>
              <td style={{ padding: '12px 8px' }}>
                <span className={s.attendance_status === 'On-Time' ? 'color-green' : 'color-red'}>
                  {s.attendance_status}
                </span>
                <div style={{ fontSize: 11, color: 'var(--text-dim)' }}>{s.punctuality_score}%</div>
              </td>
              <td style={{ padding: '12px 8px' }}>{s.attention_avg}%</td>
              <td style={{ padding: '12px 8px' }}>{s.qa_score}%</td>
              <td style={{ padding: '12px 8px', fontWeight: 'bold' }}>{s.final_multimodal_score}%</td>
            </tr>
          ))}
          {sorted.length === 0 && (
            <tr><td colSpan={6} style={{ textAlign: 'center', padding: 20, color: 'var(--text-dim)' }}>No students recorded yet</td></tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
