// src/hooks/useWebSocket.ts
// Connects to backend WebSocket and maintains live telemetry state.

import { useEffect, useRef, useState, useCallback } from 'react'
import type { TelemetryMessage } from '../types'

type WsStatus = 'connecting' | 'connected' | 'disconnected' | 'error'

interface UseWebSocketResult {
  telemetry: TelemetryMessage | null
  status: WsStatus
  alerts: string[]
  clearAlerts: () => void
}

// @ts-ignore
const WS_BASE = import.meta.env.VITE_WS_URL || (window.location.protocol === 'https:' ? 'wss://' : 'ws://') + window.location.host
const RECONNECT_DELAY_MS = 3000

export function useWebSocket(sessionId: string): UseWebSocketResult {
  const [telemetry, setTelemetry] = useState<TelemetryMessage | null>(null)
  const [status, setStatus]       = useState<WsStatus>('connecting')
  const [alerts, setAlerts]       = useState<string[]>([])
  const wsRef                     = useRef<WebSocket | null>(null)
  const reconnectTimer            = useRef<ReturnType<typeof setTimeout> | null>(null)

  const connect = useCallback(() => {
    if (!sessionId) return
    setStatus('connecting')
    const url = `${WS_BASE}/ws/${sessionId}`
    const ws  = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      setStatus('connected')
      console.log('[WS] Connected to', url)
    }

    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data)
        if (msg.type === 'telemetry') {
          setTelemetry(msg as TelemetryMessage)
          // Collect incoming alerts from telemetry payload
          if (msg.alerts?.length > 0) {
            setAlerts(prev => [...prev.slice(-19), ...msg.alerts])
          }
        }
      } catch {
        // ignore parse errors
      }
    }

    ws.onerror = () => setStatus('error')

    ws.onclose = () => {
      setStatus('disconnected')
      console.log('[WS] Disconnected — retrying in', RECONNECT_DELAY_MS, 'ms')
      reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY_MS)
    }
  }, [sessionId])

  useEffect(() => {
    connect()
    return () => {
      wsRef.current?.close()
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
    }
  }, [connect])

  const clearAlerts = useCallback(() => setAlerts([]), [])

  return { telemetry, status, alerts, clearAlerts }
}
