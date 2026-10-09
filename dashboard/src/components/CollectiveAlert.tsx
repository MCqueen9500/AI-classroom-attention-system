import React, { useEffect, useState } from 'react'

interface Props {
  onDismiss: () => void
}

export function CollectiveAlert({ onDismiss }: Props) {
  const [seconds, setSeconds] = useState(0)

  useEffect(() => {
    const timer = setInterval(() => setSeconds(s => s + 1), 1000)
    return () => clearInterval(timer)
  }, [])

  return (
    <div style={{
      position: 'fixed',
      top: 0, left: 0, right: 0, bottom: 0,
      background: 'rgba(239, 68, 68, 0.9)', // Tailwind red-500 with opacity
      zIndex: 9999,
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      color: '#fff',
      animation: 'pulse-bg 2s infinite'
    }}>
      <style>{`
        @keyframes pulse-bg {
          0% { background: rgba(239, 68, 68, 0.9); }
          50% { background: rgba(220, 38, 38, 0.95); }
          100% { background: rgba(239, 68, 68, 0.9); }
        }
      `}</style>
      
      <div style={{ fontSize: 64, marginBottom: 24 }}>⚠️</div>
      <h1 style={{ fontSize: 48, margin: '0 0 16px 0', textAlign: 'center' }}>
        CLASS ATTENTION CRITICAL
      </h1>
      <h2 style={{ fontSize: 24, margin: '0 0 48px 0', fontWeight: 'normal', opacity: 0.9 }}>
        Auto-Intermission Active
      </h2>
      
      <div style={{ fontSize: 20, marginBottom: 48 }}>
        Duration: {Math.floor(seconds / 60)}:{(seconds % 60).toString().padStart(2, '0')}
      </div>
      
      <button 
        onClick={onDismiss}
        style={{
          background: '#fff',
          color: '#dc2626',
          border: 'none',
          padding: '16px 32px',
          fontSize: 20,
          fontWeight: 'bold',
          borderRadius: 8,
          cursor: 'pointer',
          boxShadow: '0 4px 6px rgba(0,0,0,0.1)'
        }}
      >
        Dismiss & Resume Session
      </button>
    </div>
  )
}
