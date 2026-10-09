// src/components/Navbar.tsx
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

export function Navbar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  return (
    <nav className="h-[72px] bg-ivory border-b border-blue/20 flex items-center justify-between px-8 relative z-50">
      {/* Left branding */}
      <div className="flex items-center gap-4">
        <div className="h-6 w-px bg-blue opacity-40" />
        <div>
          <h1 className="text-[14px] tracking-[0.25em] uppercase font-black text-blue leading-tight">ClassMon</h1>
          <p className="text-[9px] tracking-widest uppercase text-blue opacity-50">Attention Monitor</p>
        </div>
      </div>

      {/* Center status (optional/decorative) */}
      <div className="hidden md:flex items-center gap-2">
        <div className="w-1.5 h-1.5 rounded-full bg-coral animate-pulse" />
        <span className="text-[9px] tracking-[0.2em] uppercase text-blue opacity-60">System Live</span>
      </div>

      {/* Right user & actions */}
      <div className="flex items-center gap-6">
        <div className="text-right">
          <p className="text-[11px] tracking-wider uppercase font-bold text-blue">{user?.name || 'Teacher'}</p>
          <p className="text-[9px] tracking-widest uppercase text-blue opacity-50">{user?.is_admin ? 'Administrator' : 'Educator'}</p>
        </div>
        
        <div className="h-6 w-px bg-blue opacity-20" />
        
        <button 
          onClick={logout}
          className="text-[10px] tracking-widest uppercase text-coral font-bold hover:opacity-70 transition-opacity"
        >
          Logout
        </button>
      </div>
    </nav>
  )
}
