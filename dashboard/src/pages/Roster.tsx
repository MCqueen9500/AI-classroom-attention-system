import { useEffect, useState } from 'react'
import { StudentModal } from '../components/StudentModal'

interface Student {
  roll_no: number
  name: string
  class_div: string
}

export function Roster() {
  const [students, setStudents] = useState<Student[]>([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [selectedRoll, setSelectedRoll] = useState<number | null>(null)

  useEffect(() => {
    const token = localStorage.getItem('token')
    fetch('/api/students', {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then(r => r.json())
      .then(d => {
        setStudents(d)
        setLoading(false)
      })
      .catch(console.error)
  }, [])

  const filtered = students.filter(s => 
    s.name.toLowerCase().includes(search.toLowerCase()) || 
    s.roll_no.toString().includes(search)
  )

  return (
    <div className="page-container">
      <div className="section-title">Class Roster</div>
      
      <div style={{ marginBottom: 24 }}>
        <input 
          type="text" 
          className="input" 
          placeholder="Search by name or roll number..." 
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={{ maxWidth: 400 }}
        />
      </div>

      {loading && <div>Loading roster...</div>}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: 16 }}>
        {filtered.map(s => (
          <div 
            key={s.roll_no} 
            className="card" 
            style={{ padding: 20, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 16, transition: 'transform 0.2s' }}
            onClick={() => setSelectedRoll(s.roll_no)}
          >
            <div style={{ width: 48, height: 48, borderRadius: '50%', background: 'var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 'bold' }}>
              {s.roll_no}
            </div>
            <div>
              <div style={{ fontWeight: 600 }}>{s.name}</div>
              <div style={{ fontSize: 13, color: 'var(--text-dim)' }}>Div: {s.class_div}</div>
            </div>
          </div>
        ))}
      </div>

      {filtered.length === 0 && !loading && (
        <div style={{ color: 'var(--text-dim)' }}>No students found.</div>
      )}

      {selectedRoll !== null && (
        <StudentModal rollNo={selectedRoll} onClose={() => setSelectedRoll(null)} />
      )}
    </div>
  )
}
