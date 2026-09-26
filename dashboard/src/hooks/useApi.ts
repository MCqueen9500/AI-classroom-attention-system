// src/hooks/useApi.ts
// REST API calls to backend

import { useState, useCallback } from 'react'
import type { Session, StudentScore, AttentionPoint } from '../types'

// @ts-ignore
const API = (import.meta.env.VITE_API_URL || '') + '/api'

export function useApi() {
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState<string | null>(null)

  const request = useCallback(async <T>(
    url: string, options?: RequestInit
  ): Promise<T | null> => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(API + url, {
        headers: { 'Content-Type': 'application/json' },
        ...options,
      })
      if (!res.ok) {
        setError(`HTTP ${res.status}: ${res.statusText}`)
        return null
      }
      return await res.json() as T
    } catch (e) {
      setError(String(e))
      return null
    } finally {
      setLoading(false)
    }
  }, [])

  const getActiveSesion = () =>
    request<Session>('/sessions/active')

  const listSessions = () =>
    request<Session[]>('/sessions')

  const createSession = (subject: string, start: string, end: string) =>
    request<Session>('/sessions', {
      method: 'POST',
      body: JSON.stringify({ subject_name: subject, scheduled_start: start, scheduled_end: end }),
    })

  const pauseSession  = (id: string) =>
    request(`/sessions/${id}/pause`, { method: 'PATCH', body: '{}' })

  const resumeSession = (id: string) =>
    request(`/sessions/${id}/resume`, { method: 'PATCH' })

  const getStudentScore = (roll: number, sessionId?: string) =>
    request<StudentScore>(`/students/${roll}/score${sessionId ? `?session_id=${sessionId}` : ''}`)

  const getAttentionHistory = (sessionId: string, roll?: number) =>
    request<{ points: AttentionPoint[] }>(
      `/sessions/${sessionId}/attention${roll != null ? `?roll_no=${roll}` : ''}`
    )

  return {
    loading, error,
    getActiveSesion, listSessions, createSession,
    pauseSession, resumeSession,
    getStudentScore, getAttentionHistory,
  }
}
