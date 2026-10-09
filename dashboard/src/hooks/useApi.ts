// src/hooks/useApi.ts
// REST API calls to backend

import { useState, useCallback } from 'react'
import type { Session, StudentScore, AttentionPoint } from '../types'

// @ts-ignore
const API = (import.meta.env.VITE_API_URL || '') + '/api'

function authHeader(): Record<string, string> {
  const token = localStorage.getItem('token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export interface AdminStats {
  total_teachers: number
  total_students: number
  total_sessions: number
  school_avg_attention: number
}

export interface DivisionStat {
  division: string
  avg_attention: number
}

export interface TeacherRecord {
  id: number
  name: string
  username: string
  subject: string
  division: string
}

export interface CreateTeacherPayload {
  name: string
  username: string
  password: string
  subject: string
  division: string
}

export function useApi() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const request = useCallback(async <T>(
    url: string, options?: RequestInit
  ): Promise<T | null> => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(API + url, {
        headers: {
          'Content-Type': 'application/json',
          ...authHeader(),
          ...(options?.headers as Record<string, string> | undefined),
        },
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

  // ── Auth ────────────────────────────────────────────────────────────────
  const getMe = () =>
    request<{ username: string; name: string; is_admin: boolean }>('/auth/me')

  // ── Sessions ────────────────────────────────────────────────────────────
  const getActiveSesion = () =>
    request<Session>('/sessions/active')

  const listSessions = () =>
    request<Session[]>('/sessions')

  const createSession = (
    subject: string, start: string, end: string,
    teacher: string = 'Teacher', div: string = 'A', room: string = '101'
  ) =>
    request<Session>('/sessions', {
      method: 'POST',
      body: JSON.stringify({
        subject_name: subject,
        scheduled_start: start,
        scheduled_end: end,
        teacher_name: teacher,
        class_div: div,
        room_no: room,
      }),
    })

  const endSession = (id: string) =>
    request<Session>(`/sessions/${id}/end`, { method: 'PATCH' })

  const pauseSession = (id: string) =>
    request(`/sessions/${id}/pause`, { method: 'PATCH', body: '{}' })

  const resumeSession = (id: string) =>
    request(`/sessions/${id}/resume`, { method: 'PATCH' })

  // ── Students ────────────────────────────────────────────────────────────
  const getStudentScore = (roll: number, sessionId?: string) =>
    request<StudentScore>(`/students/${roll}/score${sessionId ? `?session_id=${sessionId}` : ''}`)

  const getAttentionHistory = (sessionId: string, roll?: number) =>
    request<{ points: AttentionPoint[] }>(
      `/sessions/${sessionId}/attention${roll != null ? `?roll_no=${roll}` : ''}`
    )

  const getSessionAttendance = (sessionId: string) =>
    request<Array<{roll_no: number; name: string; status: string; punctuality_score: number}>>(
      `/sessions/${sessionId}/attendance`
    )

  // ── Admin ───────────────────────────────────────────────────────────────
  const getAdminStats = () =>
    request<AdminStats>('/admin/stats')

  const getDivisionStats = () =>
    request<DivisionStat[]>('/admin/stats/divisions')

  const getAdminTeachers = () =>
    request<TeacherRecord[]>('/admin/teachers')

  const createTeacher = (data: CreateTeacherPayload) =>
    request<TeacherRecord>('/admin/teachers', {
      method: 'POST',
      body: JSON.stringify(data),
    })

  return {
    loading, error,
    getMe,
    getActiveSesion, listSessions, createSession,
    pauseSession, resumeSession, endSession,
    getStudentScore, getAttentionHistory, getSessionAttendance,
    getAdminStats, getDivisionStats, getAdminTeachers, createTeacher,
  }
}
