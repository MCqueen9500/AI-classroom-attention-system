// src/pages/Login.tsx
// Editorial redesign — strict 3-color palette:
//   Warm Ivory:   #F5F2EB
//   Deep Blue:    #1A3C61
//   Coral Orange: #FC6C54

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
/* ─── SVG: Branching organic data-tree ──────────────────────────────────── */
function CoralTree() {
  type Pt = [number, number]
  const leafNodes: Pt[] = [
    [10,100],[50,105],[75,80],[125,85],[130,90],
    [190,95],[185,55],[230,60],[265,65],[305,70],
  ]
  const junctions: Pt[] = [
    [160,380],[160,350],[160,320],[80,260],[240,230],[160,180],
  ]
  return (
    <svg viewBox="0 0 320 520" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full h-full" aria-hidden="true">
      {/* Trunk */}
      <line x1="160" y1="500" x2="160" y2="320" stroke="#FC6C54" strokeWidth="4" strokeLinecap="round"/>
      {/* Primary */}
      <line x1="160" y1="380" x2="80"  y2="260" stroke="#FC6C54" strokeWidth="3.5" strokeLinecap="round"/>
      <line x1="160" y1="350" x2="240" y2="230" stroke="#FC6C54" strokeWidth="3.5" strokeLinecap="round"/>
      <line x1="160" y1="320" x2="160" y2="180" stroke="#FC6C54" strokeWidth="3"   strokeLinecap="round"/>
      {/* Secondary */}
      <line x1="80"  y1="260" x2="30"  y2="170" stroke="#FC6C54" strokeWidth="2.5" strokeLinecap="round"/>
      <line x1="80"  y1="260" x2="100" y2="160" stroke="#FC6C54" strokeWidth="2.5" strokeLinecap="round"/>
      <line x1="240" y1="230" x2="210" y2="130" stroke="#FC6C54" strokeWidth="2.5" strokeLinecap="round"/>
      <line x1="240" y1="230" x2="285" y2="145" stroke="#FC6C54" strokeWidth="2.5" strokeLinecap="round"/>
      {/* Tertiary */}
      <line x1="30"  y1="170" x2="10"  y2="100" stroke="#FC6C54" strokeWidth="2" strokeLinecap="round"/>
      <line x1="30"  y1="170" x2="50"  y2="105" stroke="#FC6C54" strokeWidth="2" strokeLinecap="round"/>
      <line x1="100" y1="160" x2="75"  y2="80"  stroke="#FC6C54" strokeWidth="2" strokeLinecap="round"/>
      <line x1="100" y1="160" x2="125" y2="85"  stroke="#FC6C54" strokeWidth="2" strokeLinecap="round"/>
      <line x1="160" y1="180" x2="130" y2="90"  stroke="#FC6C54" strokeWidth="2" strokeLinecap="round"/>
      <line x1="160" y1="180" x2="190" y2="95"  stroke="#FC6C54" strokeWidth="2" strokeLinecap="round"/>
      <line x1="210" y1="130" x2="185" y2="55"  stroke="#FC6C54" strokeWidth="2" strokeLinecap="round"/>
      <line x1="210" y1="130" x2="230" y2="60"  stroke="#FC6C54" strokeWidth="2" strokeLinecap="round"/>
      <line x1="285" y1="145" x2="265" y2="65"  stroke="#FC6C54" strokeWidth="2" strokeLinecap="round"/>
      <line x1="285" y1="145" x2="305" y2="70"  stroke="#FC6C54" strokeWidth="2" strokeLinecap="round"/>
      {/* Filled leaf nodes */}
      {leafNodes.map(([cx, cy]: Pt, i: number) => (
        <circle key={'leaf' + String(i)} cx={cx} cy={cy} r={5} fill="#FC6C54"/>
      ))}
      {/* Hollow junction rings */}
      {junctions.map(([cx, cy]: Pt, i: number) => (
        <circle key={'junc' + String(i)} cx={cx} cy={cy} r={6} stroke="#FC6C54" strokeWidth={1.5} fill="none"/>
      ))}
    </svg>
  )
}

/* ─── Login page ────────────────────────────────────────────────────────── */
export function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError]       = useState('')
  const [busy, setBusy]         = useState(false)

  const navigate  = useNavigate()
  const { login } = useAuth()

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      })
      if (res.ok) {
        const data = await res.json() as {
          token: string; is_admin: boolean; name: string
          username: string; subject?: string; division?: string
        }
        login(data.token, {
          username: data.username, name: data.name,
          is_admin: data.is_admin, subject: data.subject, division: data.division,
        })
        navigate(data.is_admin ? '/admin' : '/dashboard', { replace: true })
      } else {
        const body = await res.json().catch(() => ({}))
        setError((body as { detail?: string }).detail ?? 'Invalid credentials')
      }
    } catch {
      setError('Connection failed — is the backend running?')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="relative w-screen h-screen overflow-hidden bg-[#F5F2EB] flex">

      {/* ── Top navigation bar ───────────────────────────────────────── */}
      <nav className="absolute top-0 left-0 right-0 z-20 flex items-center justify-between px-10 py-7">
        {/* Left micro-copy */}
        <div className="flex items-center gap-3">
          <div className="h-5 w-px bg-[#1A3C61] opacity-40" />
          <span className="text-[10px] tracking-widest-xl uppercase text-[#1A3C61] font-semibold opacity-60">
            AI Classroom Monitoring System
          </span>
        </div>

        {/* Nav links */}
        <div className="hidden md:flex items-center gap-8">
          {['About', 'Documentation', 'Contact'].map(link => (
            <span key={link} className="text-[10px] tracking-widest-xl uppercase text-[#1A3C61] font-semibold opacity-50 hover:opacity-100 cursor-pointer transition-opacity">
              {link}
            </span>
          ))}
        </div>

        {/* Hamburger */}
        <button className="flex flex-col gap-[5px] group" aria-label="Menu">
          <span className="w-6 h-px bg-[#1A3C61] block transition-all group-hover:w-8"/>
          <span className="w-4 h-px bg-[#1A3C61] block transition-all group-hover:w-8"/>
          <span className="w-6 h-px bg-[#1A3C61] block transition-all group-hover:w-8"/>
        </button>
      </nav>

      {/* ── Left side — Hero text + form ────────────────────────────── */}
      <div className="relative z-10 flex flex-col justify-between w-1/2 px-10 md:px-16 pt-28 pb-10">

        {/* Hero stacked title */}
        <div className="select-none">
          <div
            className="text-[clamp(52px,7.5vw,110px)] font-black leading-none tracking-tight text-[#1A3C61] uppercase"
          >
            CLASS
          </div>
          <div
            className="text-[clamp(52px,7.5vw,110px)] font-black leading-none tracking-tight text-stroke-blue uppercase"
          >
            CLASS
          </div>
          <div
            className="text-[clamp(52px,7.5vw,110px)] font-black leading-none tracking-tight text-[#1A3C61] uppercase"
          >
            CLASS
          </div>

          {/* Sub-label with line accent */}
          <div className="flex items-center gap-3 mt-6 ml-1">
            <div className="w-8 h-px bg-[#FC6C54]" />
            <span className="text-[11px] tracking-widest-xl uppercase text-[#1A3C61] font-medium opacity-60">
              Mon · Attention Monitor
            </span>
          </div>
        </div>

        {/* Login form */}
        <div className="mb-4 max-w-xs">
          {/* Metadata strip */}
          <div className="flex items-center gap-3 mb-7">
            <div className="w-px h-10 bg-[#1A3C61] opacity-30" />
            <div>
              <p className="text-[10px] tracking-widest-xl uppercase text-[#1A3C61] opacity-50 font-semibold">
                Sign in
              </p>
              <p className="text-[10px] tracking-wider uppercase text-[#1A3C61] opacity-40">
                Teacher / Administrator Portal
              </p>
            </div>
          </div>

          <form onSubmit={handleLogin} className="flex flex-col gap-4">
            {/* Username */}
            <div className="flex flex-col gap-1.5">
              <label className="text-[10px] tracking-widest-xl uppercase text-[#1A3C61] font-semibold opacity-60">
                Username
              </label>
              <input
                autoFocus
                autoComplete="username"
                value={username}
                onChange={e => setUsername(e.target.value)}
                className="bg-transparent border-b-2 border-[#1A3C61] text-[#1A3C61] placeholder-[#1A3C61]/30
                           py-2 text-sm font-medium outline-none focus:border-[#FC6C54] transition-colors"
                placeholder="your.username"
              />
            </div>

            {/* Password */}
            <div className="flex flex-col gap-1.5">
              <label className="text-[10px] tracking-widest-xl uppercase text-[#1A3C61] font-semibold opacity-60">
                Password
              </label>
              <input
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                className="bg-transparent border-b-2 border-[#1A3C61] text-[#1A3C61] placeholder-[#1A3C61]/30
                           py-2 text-sm font-medium outline-none focus:border-[#FC6C54] transition-colors"
                placeholder="••••••••"
              />
            </div>

            {/* Error */}
            {error && (
              <div className="text-[11px] text-[#FC6C54] border border-[#FC6C54]/40 bg-[#FC6C54]/5 rounded px-3 py-2 tracking-wide">
                {error}
              </div>
            )}

            {/* Submit */}
            <button
              type="submit"
              disabled={busy || !username.trim() || !password.trim()}
              className="mt-2 bg-[#1A3C61] text-[#F5F2EB] text-[11px] tracking-widest-xl uppercase font-bold
                         py-3.5 px-6 transition-all hover:bg-[#FC6C54] disabled:opacity-30 disabled:cursor-not-allowed"
            >
              {busy ? 'Authenticating…' : 'Enter →'}
            </button>
          </form>
        </div>

        {/* Bottom circular arrow button */}
        <div className="flex items-center gap-4">
          <button
            className="w-12 h-12 rounded-full border-2 border-[#1A3C61] text-[#1A3C61] flex items-center justify-center
                       hover:bg-[#1A3C61] hover:text-[#F5F2EB] transition-all"
            aria-label="Scroll"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M8 3v10M3 8l5 5 5-5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
          <div className="flex items-center gap-2">
            <div className="h-px w-5 bg-[#1A3C61] opacity-30" />
            <span className="text-[9px] tracking-widest-xl uppercase text-[#1A3C61] opacity-40">
              v2.0 · 2026
            </span>
          </div>
        </div>
      </div>

      {/* ── Right side — Deep Blue block ─────────────────────────────── */}
      <div className="relative w-1/2 bg-[#1A3C61] h-full flex flex-col justify-between px-12 py-10">

        {/* Top-right metadata */}
        <div className="flex flex-col items-end gap-2 mt-16">
          <span className="text-[10px] tracking-widest-xl uppercase text-[#F5F2EB] opacity-30 font-semibold">
            Real-time Analytics
          </span>
          <div className="w-8 h-px bg-[#F5F2EB] opacity-20" />
          <span className="text-[10px] tracking-widest-xl uppercase text-[#F5F2EB] opacity-20">
            Edge AI Pipeline
          </span>
        </div>

        {/* System stats — decorative */}
        <div className="flex flex-col gap-6 my-auto">
          {[
            { label: 'Attention Score', value: '94%' },
            { label: 'Students Tracked', value: '36' },
            { label: 'Q&A Sessions', value: '128' },
          ].map(stat => (
            <div key={stat.label} className="flex items-end justify-between border-b border-[#F5F2EB]/10 pb-4">
              <span className="text-[10px] tracking-widest-xl uppercase text-[#F5F2EB] opacity-40 font-semibold">
                {stat.label}
              </span>
              <span className="text-3xl font-black text-[#F5F2EB] opacity-20 leading-none">
                {stat.value}
              </span>
            </div>
          ))}
        </div>

        {/* Bottom-right vertical text */}
        <div className="flex items-center gap-3 self-end">
          <div className="w-px h-10 bg-[#F5F2EB] opacity-20" />
          <span
            className="text-[9px] tracking-widest-xl uppercase text-[#F5F2EB] opacity-25 font-semibold"
            style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)' }}
          >
            Powered by Whisper · Faster-Whisper · MediaPipe
          </span>
        </div>
      </div>

      {/* ── Coral tree — overlaps the boundary ───────────────────────── */}
      <div
        className="absolute z-20 pointer-events-none"
        style={{
          width:  'clamp(200px, 22vw, 340px)',
          height: 'clamp(360px, 55vh, 560px)',
          left:   'calc(50% - clamp(100px, 11vw, 170px))',
          bottom: '3vh',
        }}
      >
        <CoralTree />
      </div>

      {/* Thin vertical divider line at exact center */}
      <div
        className="absolute z-10 top-24 bottom-24 w-px bg-[#1A3C61] opacity-[0.07]"
        style={{ left: '50%' }}
      />

    </div>
  )
}
