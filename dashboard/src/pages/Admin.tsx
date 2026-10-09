// src/pages/Admin.tsx
// Admin-only page: school-level stats, division bar chart, teacher management.

import { useEffect, useState } from 'react'
import { useAuth }    from '../contexts/AuthContext'
import { useApi }     from '../hooks/useApi'
import type { AdminStats, DivisionStat, TeacherRecord, CreateTeacherPayload } from '../hooks/useApi'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from 'recharts'

// ── Helpers ──────────────────────────────────────────────────────────────────

const DIVISIONS = ['A', 'B', 'C', 'D', 'E', 'F']

const BAR_COLORS = ['#4f8ef7', '#22d3a0', '#f59e0b', '#ef4444', '#a78bfa', '#38bdf8']

// ── Stat Card ────────────────────────────────────────────────────────────────

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div style={{
      background: 'var(--card-bg)',
      border: '1px solid var(--border)',
      borderRadius: 14,
      padding: '24px 28px',
      flex: 1,
      minWidth: 180,
    }}>
      <div style={{ fontSize: 12, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 8 }}>
        {label}
      </div>
      <div style={{ fontSize: 36, fontWeight: 800, color: 'var(--accent)' }}>
        {value}
      </div>
      {sub && <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>{sub}</div>}
    </div>
  )
}

// ── Add Teacher Modal ─────────────────────────────────────────────────────────

interface AddTeacherModalProps {
  onClose: () => void
  onCreated: (t: TeacherRecord) => void
}

function AddTeacherModal({ onClose, onCreated }: AddTeacherModalProps) {
  const api = useApi()
  const [form, setForm] = useState<CreateTeacherPayload>({
    name: '', username: '', password: '', subject: '', division: 'A',
  })
  const [localError, setLocalError] = useState('')

  function setField(key: keyof CreateTeacherPayload, value: string) {
    setForm(prev => ({ ...prev, [key]: value }))
  }

  const isValid = form.name.trim() && form.username.trim() && form.password.trim()
    && form.subject.trim() && form.division

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLocalError('')
    const result = await api.createTeacher(form)
    if (result) {
      onCreated(result)
    } else {
      setLocalError(api.error ?? 'Failed to create teacher')
    }
  }

  const inputStyle: React.CSSProperties = {
    width: '100%',
    background: 'var(--bg-dark)',
    color: 'white',
    border: '1px solid var(--border)',
    borderRadius: 8,
    padding: '10px 12px',
    fontSize: 14,
    boxSizing: 'border-box',
    outline: 'none',
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 999,
    }}>
      <div style={{
        background: 'var(--card-bg)',
        border: '1px solid var(--border)',
        borderRadius: 16,
        padding: '36px 40px',
        width: 480,
        boxShadow: '0 20px 60px rgba(0,0,0,0.6)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
          <h3 style={{ margin: 0, fontSize: 20, fontWeight: 700 }}>Add Teacher</h3>
          <button
            onClick={onClose}
            style={{ background: 'none', border: 'none', color: 'var(--text-muted)', fontSize: 22, cursor: 'pointer' }}
          >×</button>
        </div>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12 }}>
              <span style={{ color: 'var(--text-muted)', textTransform: 'uppercase' }}>Full Name *</span>
              <input
                value={form.name}
                onChange={e => setField('name', e.target.value)}
                placeholder="e.g. Prof. Sharma"
                style={inputStyle}
              />
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12 }}>
              <span style={{ color: 'var(--text-muted)', textTransform: 'uppercase' }}>Username *</span>
              <input
                value={form.username}
                onChange={e => setField('username', e.target.value)}
                placeholder="e.g. sharma"
                style={inputStyle}
              />
            </label>
          </div>

          <label style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12 }}>
            <span style={{ color: 'var(--text-muted)', textTransform: 'uppercase' }}>Password *</span>
            <input
              type="password"
              value={form.password}
              onChange={e => setField('password', e.target.value)}
              placeholder="Minimum 8 characters"
              style={inputStyle}
            />
          </label>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12 }}>
              <span style={{ color: 'var(--text-muted)', textTransform: 'uppercase' }}>Subject *</span>
              <input
                value={form.subject}
                onChange={e => setField('subject', e.target.value)}
                placeholder="e.g. Computer Vision"
                style={inputStyle}
              />
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12 }}>
              <span style={{ color: 'var(--text-muted)', textTransform: 'uppercase' }}>Division *</span>
              <select
                value={form.division}
                onChange={e => setField('division', e.target.value)}
                style={{ ...inputStyle }}
              >
                {DIVISIONS.map(d => <option key={d} value={d}>Division {d}</option>)}
              </select>
            </label>
          </div>

          {localError && (
            <div style={{
              color: 'var(--red)', fontSize: 13,
              background: 'rgba(239,68,68,0.08)',
              border: '1px solid var(--red)',
              borderRadius: 6, padding: '8px 12px',
            }}>
              {localError}
            </div>
          )}

          <div style={{ display: 'flex', gap: 12, marginTop: 8 }}>
            <button
              type="button"
              className="btn"
              style={{ flex: 1, padding: '12px' }}
              onClick={onClose}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              style={{ flex: 2, padding: '12px', fontWeight: 700 }}
              disabled={api.loading || !isValid}
            >
              {api.loading ? 'Creating…' : 'Create Teacher'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ── Main Admin Page ───────────────────────────────────────────────────────────

type AdminSection = 'overview' | 'teachers' | 'reports'

export function Admin() {
  const { user, logout }    = useAuth()
  const api                 = useApi()
  const [section, setSection]     = useState<AdminSection>('overview')
  const [stats, setStats]         = useState<AdminStats | null>(null)
  const [divStats, setDivStats]   = useState<DivisionStat[]>([])
  const [teachers, setTeachers]   = useState<TeacherRecord[]>([])
  const [showAddTeacher, setShowAddTeacher] = useState(false)

  useEffect(() => {
    api.getAdminStats().then(s => { if (s) setStats(s) })
    api.getDivisionStats().then(d => { if (d) setDivStats(d) })
    api.getAdminTeachers().then(t => { if (t) setTeachers(t) })
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  function handleTeacherCreated(t: TeacherRecord) {
    setTeachers(prev => [...prev, t])
    setShowAddTeacher(false)
  }

  // ── Sidebar items ──────────────────────────────────────────────────────
  const sidebarItems: { id: AdminSection; label: string; icon: string }[] = [
    { id: 'overview',  label: 'Overview',  icon: '📊' },
    { id: 'teachers',  label: 'Teachers',  icon: '👩‍🏫' },
    { id: 'reports',   label: 'Reports',   icon: '📈' },
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: 'var(--bg-dark)' }}>

      {/* ── Navbar ── */}
      <header style={{
        display: 'flex', alignItems: 'center',
        padding: '0 24px', height: 60,
        background: 'var(--card-bg)',
        borderBottom: '1px solid var(--border)',
        gap: 16, flexShrink: 0,
      }}>
        <div style={{ fontWeight: 800, fontSize: 20, color: 'var(--accent)', letterSpacing: -0.5 }}>
          ClassMon <span style={{ color: 'var(--text-muted)', fontWeight: 400, fontSize: 13, letterSpacing: 0 }}>Admin</span>
        </div>
        <div style={{ flex: 1 }} />
        {user && (
          <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>
            Signed in as <strong style={{ color: 'white' }}>{user.name}</strong>
          </div>
        )}
        <button
          className="btn"
          style={{ padding: '6px 16px', fontSize: 13 }}
          onClick={logout}
        >
          Logout
        </button>
      </header>

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>

        {/* ── Sidebar ── */}
        <aside style={{
          width: 220, background: 'var(--card-bg)',
          borderRight: '1px solid var(--border)',
          padding: '24px 0', flexShrink: 0,
          display: 'flex', flexDirection: 'column', gap: 4,
        }}>
          {sidebarItems.map(item => (
            <button
              key={item.id}
              onClick={() => setSection(item.id)}
              style={{
                display: 'flex', alignItems: 'center', gap: 12,
                padding: '12px 20px', border: 'none', borderRadius: 0,
                background: section === item.id
                  ? 'rgba(79,142,247,0.12)'
                  : 'transparent',
                color: section === item.id ? 'var(--accent)' : 'var(--text-muted)',
                fontWeight: section === item.id ? 700 : 400,
                fontSize: 14, cursor: 'pointer',
                textAlign: 'left', width: '100%',
                borderLeft: section === item.id
                  ? '3px solid var(--accent)'
                  : '3px solid transparent',
                transition: 'all 0.15s',
              }}
            >
              <span>{item.icon}</span>
              {item.label}
            </button>
          ))}
        </aside>

        {/* ── Main Content ── */}
        <main style={{ flex: 1, overflowY: 'auto', padding: 32 }}>

          {/* ── OVERVIEW ── */}
          {section === 'overview' && (
            <>
              <h2 style={{ margin: '0 0 24px', fontSize: 22 }}>School Overview</h2>

              {/* Stat Cards */}
              <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap', marginBottom: 32 }}>
                <StatCard
                  label="Total Teachers"
                  value={stats?.total_teachers ?? '—'}
                  sub="registered teachers"
                />
                <StatCard
                  label="Total Students"
                  value={stats?.total_students ?? '—'}
                  sub="enrolled students"
                />
                <StatCard
                  label="Total Sessions"
                  value={stats?.total_sessions ?? '—'}
                  sub="all-time sessions"
                />
                <StatCard
                  label="School Avg Attention"
                  value={stats ? `${Math.round(stats.school_avg_attention)}%` : '—'}
                  sub="across all sessions"
                />
              </div>

              {/* Division Bar Chart */}
              <div style={{
                background: 'var(--card-bg)',
                border: '1px solid var(--border)',
                borderRadius: 14,
                padding: '24px 28px',
              }}>
                <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 20 }}>
                  Average Attention by Division
                </div>
                {divStats.length === 0 ? (
                  <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '40px 0', fontSize: 14 }}>
                    No division data yet.
                  </div>
                ) : (
                  <ResponsiveContainer width="100%" height={280}>
                    <BarChart data={divStats} barSize={40}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                      <XAxis
                        dataKey="division"
                        tick={{ fill: 'var(--text-muted)', fontSize: 13 }}
                        axisLine={{ stroke: 'var(--border)' }}
                        tickLine={false}
                        tickFormatter={v => `Div ${v}`}
                      />
                      <YAxis
                        domain={[0, 100]}
                        tick={{ fill: 'var(--text-muted)', fontSize: 12 }}
                        axisLine={false}
                        tickLine={false}
                        tickFormatter={v => `${v}%`}
                      />
                      <Tooltip
                        contentStyle={{
                          background: 'var(--card-bg)',
                          border: '1px solid var(--border)',
                          borderRadius: 8,
                          color: 'white',
                        }}
                        formatter={(v) => [`${Math.round(Number(v))}%`, 'Avg Attention']}
                        labelFormatter={l => `Division ${l}`}
                      />
                      <Bar dataKey="avg_attention" radius={[6, 6, 0, 0]}>
                        {divStats.map((_, i) => (
                          <Cell key={i} fill={BAR_COLORS[i % BAR_COLORS.length]} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </div>
            </>
          )}

          {/* ── TEACHERS ── */}
          {section === 'teachers' && (
            <>
              <div style={{ display: 'flex', alignItems: 'center', marginBottom: 24, gap: 16 }}>
                <h2 style={{ margin: 0, fontSize: 22 }}>Teachers</h2>
                <div style={{ flex: 1 }} />
                <button
                  className="btn btn-primary"
                  style={{ padding: '8px 20px', fontWeight: 700 }}
                  onClick={() => setShowAddTeacher(true)}
                >
                  + Add Teacher
                </button>
              </div>

              <div style={{
                background: 'var(--card-bg)',
                border: '1px solid var(--border)',
                borderRadius: 14,
                overflow: 'hidden',
              }}>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border)' }}>
                      {['Name', 'Username', 'Subject', 'Division'].map(col => (
                        <th key={col} style={{
                          padding: '14px 20px', textAlign: 'left',
                          fontSize: 12, color: 'var(--text-muted)',
                          textTransform: 'uppercase', letterSpacing: 0.8,
                          fontWeight: 600,
                        }}>
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {teachers.length === 0 ? (
                      <tr>
                        <td colSpan={4} style={{
                          padding: '48px', textAlign: 'center',
                          color: 'var(--text-muted)', fontSize: 14,
                        }}>
                          No teachers found. Click <strong>+ Add Teacher</strong> to get started.
                        </td>
                      </tr>
                    ) : teachers.map((t, i) => (
                      <tr key={t.id} style={{
                        borderBottom: i < teachers.length - 1 ? '1px solid var(--border)' : 'none',
                        transition: 'background 0.15s',
                      }}
                        onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.03)')}
                        onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                      >
                        <td style={{ padding: '14px 20px', fontWeight: 600 }}>{t.name}</td>
                        <td style={{ padding: '14px 20px', color: 'var(--text-muted)', fontFamily: 'monospace', fontSize: 13 }}>
                          {t.username}
                        </td>
                        <td style={{ padding: '14px 20px' }}>{t.subject}</td>
                        <td style={{ padding: '14px 20px' }}>
                          <span style={{
                            display: 'inline-block',
                            background: 'rgba(79,142,247,0.12)',
                            color: 'var(--accent)',
                            borderRadius: 6,
                            padding: '2px 10px',
                            fontSize: 13,
                            fontWeight: 700,
                          }}>
                            Div {t.division}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}

          {/* ── REPORTS ── */}
          {section === 'reports' && (
            <>
              <h2 style={{ margin: '0 0 24px', fontSize: 22 }}>Reports</h2>

              {/* Division breakdown table */}
              <div style={{
                background: 'var(--card-bg)',
                border: '1px solid var(--border)',
                borderRadius: 14,
                padding: '24px 28px',
                marginBottom: 24,
              }}>
                <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 20 }}>
                  Division Attention Breakdown
                </div>
                {divStats.length === 0 ? (
                  <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '32px 0', fontSize: 14 }}>
                    No data available yet.
                  </div>
                ) : (
                  <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--border)' }}>
                        <th style={{ padding: '12px 16px', textAlign: 'left', fontSize: 12, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.8 }}>Division</th>
                        <th style={{ padding: '12px 16px', textAlign: 'left', fontSize: 12, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.8 }}>Avg Attention</th>
                        <th style={{ padding: '12px 16px', textAlign: 'left', fontSize: 12, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.8 }}>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {divStats.map((d, i) => {
                        const pct = Math.round(d.avg_attention)
                        const color = pct >= 75 ? 'var(--green)' : pct >= 50 ? '#f59e0b' : 'var(--red)'
                        return (
                          <tr key={d.division} style={{ borderBottom: i < divStats.length - 1 ? '1px solid var(--border)' : 'none' }}>
                            <td style={{ padding: '14px 16px', fontWeight: 700 }}>Division {d.division}</td>
                            <td style={{ padding: '14px 16px' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                                <div style={{
                                  height: 8, borderRadius: 4, flex: 1, background: 'var(--border)',
                                  overflow: 'hidden', maxWidth: 200,
                                }}>
                                  <div style={{ height: '100%', width: `${pct}%`, background: color, borderRadius: 4 }} />
                                </div>
                                <span style={{ fontWeight: 700, color, minWidth: 40 }}>{pct}%</span>
                              </div>
                            </td>
                            <td style={{ padding: '14px 16px' }}>
                              <span style={{
                                fontSize: 12, fontWeight: 600, padding: '3px 10px', borderRadius: 99,
                                background: pct >= 75
                                  ? 'rgba(34,211,160,0.12)'
                                  : pct >= 50
                                  ? 'rgba(245,158,11,0.12)'
                                  : 'rgba(239,68,68,0.12)',
                                color,
                              }}>
                                {pct >= 75 ? '✓ Good' : pct >= 50 ? '⚠ Moderate' : '✕ Low'}
                              </span>
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                )}
              </div>
            </>
          )}

        </main>
      </div>

      {showAddTeacher && (
        <AddTeacherModal
          onClose={() => setShowAddTeacher(false)}
          onCreated={handleTeacherCreated}
        />
      )}
    </div>
  )
}
