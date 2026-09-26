// src/types/index.ts
// TypeScript types that mirror the backend Pydantic schemas exactly

export interface FaceData {
  roll_no: number
  slot: number
  h_i: number       // head pose score
  g_i: number       // eye gaze / EAR score
  p_i: number       // posture score
  a_i: number       // instantaneous attention = 0.30H + 0.50G + 0.20P
  is_drowsy: boolean
  is_speaking: boolean
  confidence: number
  bbox: [number, number, number, number]
}

export interface QAWindowStatus {
  active: boolean
  asked_roll: number | null
  question_text: string | null
  seconds_remaining: number
  speaker_roll: number | null
  wrong_student: boolean
}

export interface TelemetryMessage {
  type: 'telemetry'
  timestamp: string
  session_id: string
  class_attention_pct: number
  face_count: number
  faces: FaceData[]
  qa_window: QAWindowStatus
  alerts: string[]
  is_paused: boolean
}

export interface AlertMessage {
  type: 'alert'
  timestamp: string
  alert_type: string
  roll_no: number | null
  detail: string
}

export type WsMessage = TelemetryMessage | AlertMessage

export interface Session {
  session_id: string
  subject_name: string
  scheduled_start: string
  scheduled_end: string
  is_active: boolean
}

export interface StudentScore {
  roll_no: number
  name: string
  punctuality_score: number
  attention_avg: number
  qa_score: number
  final_score_pct: number
  total_logs: number
}

export interface AttentionPoint {
  timestamp: string
  attention_avg: number
  face_count: number
}
