"""
backend/api/routes/telemetry.py
================================
Endpoint to receive live telemetry from the external Vision/Audio pipelines
and push it into the in-memory pipeline_state for the WebSocket to broadcast.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional
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

class AudioPush(BaseModel):
    qa_active: bool = False
    qa_asked_roll: Optional[int] = None
    qa_question: Optional[str] = None
    qa_seconds: float = 0.0
    qa_speaker: Optional[int] = None
    qa_wrong: bool = False

@router.post("/audio")
async def push_audio(data: AudioPush):
    """Audio pipeline calls this to update QA state."""
    qa = LiveQAState(
        active=data.qa_active,
        asked_roll=data.qa_asked_roll,
        question_text=data.qa_question,
        seconds_remaining=data.qa_seconds,
        speaker_roll=data.qa_speaker,
        wrong_student=data.qa_wrong
    )
    pipeline_state.update_qa_window(qa)
    return {"status": "ok"}


from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from db.session import get_db

class AttentionLogPayload(BaseModel):
    session_id: str
    roll_no: int
    h_i: float
    g_i: float
    p_i: float
    confidence: float

@router.post('/log')
async def log_telemetry(payload: AttentionLogPayload, db: AsyncSession = Depends(get_db)):
    from db.crud import log_visual_attention
    await log_visual_attention(
        db=db,
        session_id=payload.session_id,
        roll_no=payload.roll_no,
        h_i=payload.h_i,
        g_i=payload.g_i,
        p_i=payload.p_i,
        confidence=payload.confidence
    )
    return {'status': 'logged'}
