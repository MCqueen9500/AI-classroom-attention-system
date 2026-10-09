"""
backend/api/schemas.py
========================
Pydantic models for all API request/response bodies.
These define exactly what JSON the server sends and receives.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime
from uuid import UUID


# ---------------------------------------------------------------------------
# WebSocket Telemetry Message (broadcast every 500ms)
# ---------------------------------------------------------------------------

class FaceData(BaseModel):
    """Per-face attention data for one student in one frame."""
    roll_no:    int
    slot:       int            # position index in frame
    h_i:        float          # head pose score
    g_i:        float          # eye gaze / EAR score
    p_i:        float          # posture score
    a_i:        float          # instantaneous attention
    is_drowsy:  bool
    is_speaking: bool          # lip activity detected
    confidence: float
    bbox:       List[int]      # [x, y, w, h]

class QAWindowStatus(BaseModel):
    """Current state of the Q&A response window."""
    active:            bool
    asked_roll:        Optional[int]   = None
    question_text:     Optional[str]   = None
    seconds_remaining: float           = 0.0
    speaker_roll:      Optional[int]   = None   # who is actually speaking
    wrong_student:     bool            = False

class TelemetryMessage(BaseModel):
    """
    Main WebSocket broadcast message sent every 500ms.
    Contains everything the dashboard needs to update live.
    """
    type:                str = "telemetry"
    timestamp:           str
    session_id:          str
    class_attention_pct: float
    face_count:          int
    faces:               List[FaceData]
    qa_window:           QAWindowStatus
    alerts:              List[str]       = []
    is_paused:           bool           = False


# ---------------------------------------------------------------------------
# Alert Message (sent immediately on events)
# ---------------------------------------------------------------------------

class AlertMessage(BaseModel):
    type:        str = "alert"
    timestamp:   str
    alert_type:  str    # "WRONG_STUDENT" | "DROWSY" | "COLLECTIVE_DISTRACTION" | "QA_COMPLETE"
    roll_no:     Optional[int] = None
    detail:      str = ""


# ---------------------------------------------------------------------------
# Session Schemas
# ---------------------------------------------------------------------------

class SessionCreate(BaseModel):
    subject_name:    str
    teacher_name:    str = "Teacher"
    class_div:       str = "A"
    room_no:         str = "101"
    scheduled_start: datetime
    scheduled_end:   datetime

class SessionResponse(BaseModel):
    session_id:      str
    subject_name:    str
    teacher_name:    str = "Teacher"
    class_div:       str = "A"
    room_no:         str = "101"
    scheduled_start: datetime
    scheduled_end:   datetime
    is_active:       bool

    class Config:
        from_attributes = True



# ---------------------------------------------------------------------------
# Student Schemas
# ---------------------------------------------------------------------------

class StudentResponse(BaseModel):
    roll_no:   int
    name:      str
    class_div: Optional[str] = None

    class Config:
        from_attributes = True

class StudentScoreResponse(BaseModel):
    roll_no:           int
    name:              str
    punctuality_score: float
    attention_avg:     float
    qa_score:          float
    final_score_pct:   float
    total_logs:        int


# ---------------------------------------------------------------------------
# Attention History (for timeline graph)
# ---------------------------------------------------------------------------

class AttentionPoint(BaseModel):
    """One data point for the per-minute attention timeline graph."""
    timestamp:      str
    attention_avg:  float
    face_count:     int

class AttentionHistoryResponse(BaseModel):
    session_id:  str
    roll_no:     Optional[int] = None   # None = class average
    points:      List[AttentionPoint]


# ---------------------------------------------------------------------------
# QA Interaction Schema
# ---------------------------------------------------------------------------

class QAInteractionResponse(BaseModel):
    interaction_id:   int
    roll_no:          int
    student_name:     Optional[str] = None
    question_text:    Optional[str] = None
    student_responded: bool
    teacher_interrupted: bool
    qa_score:         float
    score_reason:     Optional[str] = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Pause / Resume
# ---------------------------------------------------------------------------

class PauseRequest(BaseModel):
    trigger_type: str = "MANUAL"   # MANUAL | AUTO_COLLECTIVE_ANOMALY

class ResumeResponse(BaseModel):
    session_id:    str
    resumed_at:    str
    message:       str
