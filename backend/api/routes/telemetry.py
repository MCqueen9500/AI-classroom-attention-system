"""
backend/api/routes/telemetry.py
================================
Endpoint to receive live telemetry from the external Vision/Audio pipelines
and push it into the in-memory pipeline_state for the WebSocket to broadcast.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy import select
from api.pipeline_state import pipeline_state, LiveFaceState, LiveQAState

router = APIRouter(prefix="/api/telemetry", tags=["Telemetry"])

class TelemetryFace(BaseModel):
    roll_no: int
    slot: int
    h_i: float
    g_i: float
    p_i: float
    a_i: float
    is_drowsy: bool
    is_speaking: bool
    confidence: float
    bbox: List[int]
    mar: Optional[float] = 0.0

class TelemetryPush(BaseModel):
    session_id: str
    class_attention_pct: float
    faces: List[TelemetryFace]

@router.post("/vision")
async def push_vision(data: TelemetryPush):
    """Vision pipeline calls this to update face state."""
    pipeline_state.set_session(data.session_id)
    faces = [
        LiveFaceState(
            roll_no=f.roll_no,
            slot=f.slot,
            h_i=f.h_i,
            g_i=f.g_i,
            p_i=f.p_i,
            a_i=f.a_i,
            is_drowsy=f.is_drowsy,
            is_speaking=f.is_speaking,
            confidence=f.confidence,
            bbox=f.bbox
        ) for f in data.faces
    ]
    pipeline_state.update_faces(faces, data.class_attention_pct)
    return {"status": "ok"}

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from db.session import get_db

class AudioPush(BaseModel):
    qa_active: bool = False
    qa_asked_roll: Optional[int] = None
    qa_question: Optional[str] = None
    qa_seconds: float = 0.0
    qa_speaker: Optional[int] = None
    qa_wrong: bool = False
    student_response_text: Optional[str] = None
    llm_feedback: Optional[str] = None
    qa_score: Optional[float] = None
    session_id: Optional[str] = None

@router.post("/audio")
async def push_audio(data: AudioPush, db: AsyncSession = Depends(get_db)):
    """Audio pipeline calls this to update QA state."""
    print(f"[API] 📡 Received Q&A state from Audio Pipeline: active={data.qa_active}, roll={data.qa_asked_roll}")
    qa = LiveQAState(
        active=data.qa_active,
        asked_roll=data.qa_asked_roll,
        question_text=data.qa_question,
        seconds_remaining=data.qa_seconds,
        speaker_roll=data.qa_speaker,
        wrong_student=data.qa_wrong
    )
    pipeline_state.update_qa_window(qa)
    
    if not data.qa_active and data.qa_score is not None and data.session_id and data.qa_asked_roll:
        from db.crud import log_qa_interaction
        await log_qa_interaction(
            db=db,
            session_id=data.session_id,
            roll_no=data.qa_asked_roll,
            student_responded=(data.qa_score > 0.0),
            qa_score=data.qa_score,
            question_text=data.qa_question,
            student_response_text=data.student_response_text,
            llm_feedback=data.llm_feedback,
        )
    return {"status": "ok"}

class AttentionLogPayload(BaseModel):
    session_id: str
    roll_no: int
    h_i: float
    g_i: float
    p_i: float
    confidence: float
    mar: Optional[float] = 0.0

@router.post('/log')
async def log_telemetry(payload: AttentionLogPayload, db: AsyncSession = Depends(get_db)):
    from db.crud import log_visual_attention, record_attendance
    from db.models import AttendanceRecord
    from sqlalchemy import and_

    # ── Auto-attendance: record on first sighting of a recognised face ───
    # roll_no > 0 means face was matched to a known student
    if payload.roll_no > 0:
        existing = await db.execute(
            select(AttendanceRecord).where(
                and_(
                    AttendanceRecord.session_id == payload.session_id,
                    AttendanceRecord.roll_no == payload.roll_no,
                )
            )
        )
        if existing.scalar_one_or_none() is None:
            # First time this student is seen → mark attendance now
            await record_attendance(db, payload.session_id, payload.roll_no)

        await log_visual_attention(
            db=db,
            session_id=payload.session_id,
            roll_no=payload.roll_no,
            head_pose_score=payload.h_i,
            eye_gaze_score=payload.g_i,
            posture_score=payload.p_i,
            confidence=payload.confidence,
            mar=payload.mar
        )
    return {'status': 'logged'}


# ---------------------------------------------------------------------------
# Q&A Interaction Log — write final Q&A result to DB
# ---------------------------------------------------------------------------
class QALogPayload(BaseModel):
    session_id:          str
    roll_no:             int
    question_text:       Optional[str] = None
    qa_score:            float = 0.0
    student_responded:   bool  = False
    teacher_interrupted: bool  = False

@router.post('/qa_log')
async def log_qa_interaction(payload: QALogPayload, db: AsyncSession = Depends(get_db)):
    """
    Write a completed Q&A interaction to the database.
    Called by the audio pipeline after a Q&A window closes,
    or by the manual test script.
    """
    from db import crud
    await crud.log_qa_interaction(
        db=db,
        session_id=payload.session_id,
        roll_no=payload.roll_no,
        qa_score=payload.qa_score,
        student_responded=payload.student_responded,
        teacher_interrupted=payload.teacher_interrupted,
    )
    return {'status': 'logged', 'roll_no': payload.roll_no, 'qa_score': payload.qa_score}


class AttendancePush(BaseModel):
    session_id: str
    roll_no: int

@router.post('/attendance')
async def push_attendance(payload: AttendancePush, db: AsyncSession = Depends(get_db)):
    """
    Called by vision pipeline when a student accumulates 30+ recognized frames.
    Marks them Present in the DB and pushes a WebSocket alert.
    """
    from db.crud import mark_attendance_present
    from api.pipeline_state import pipeline_state
    record = await mark_attendance_present(db, payload.session_id, payload.roll_no)
    pipeline_state.add_alert(f'Roll {payload.roll_no} marked PRESENT')
    return {'status': 'marked_present', 'roll_no': payload.roll_no, 'punctuality': record.punctuality_score}


# ---------------------------------------------------------------------------
# REPAIR 4: Live state endpoint for edge pipeline MAR queries
# ---------------------------------------------------------------------------

@router.get('/state')
async def get_pipeline_state():
    """
    Returns the current in-memory pipeline state (faces + MAR + QA window).
    Called by the Audio Pipeline to perform lip-sync (MAR) verification
    before finalising a Q&A score.
    Non-destructive — does NOT consume the alerts buffer.
    """
    return pipeline_state.to_dict()
