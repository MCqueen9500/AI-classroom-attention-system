"""
backend/api/routes/sessions.py
================================
REST endpoints for session management.

GET    /api/sessions            → list sessions (filtered by teacher if not admin)
POST   /api/sessions            → create new session (stamps teacher_id from JWT)
GET    /api/sessions/{id}       → get session detail
PATCH  /api/sessions/{id}/pause  → pause (log intermission)
PATCH  /api/sessions/{id}/resume → resume session
GET    /api/sessions/{id}/attention → attention time-series (for graph)
GET    /api/sessions/{id}/qa    → list all Q&A interactions
"""

import logging
from datetime import datetime, timezone
from typing import Optional, List

import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from db.session import get_db
from db import crud
from db.models import Teacher, Session as SessionModel
from api.schemas import (
    SessionCreate, SessionResponse,
    AttentionHistoryResponse, AttentionPoint,
    QAInteractionResponse, PauseRequest, ResumeResponse,
)
from api.pipeline_state import pipeline_state

logger  = logging.getLogger(__name__)
router  = APIRouter(prefix="/api/sessions", tags=["Sessions"])

_JWT_ALGORITHM = "HS256"


# ── JWT helper ────────────────────────────────────────────────────────────────

async def _get_teacher_from_request(
    request: Request, db: AsyncSession
) -> Optional[Teacher]:
    """
    Attempt to resolve the logged-in teacher from the Authorization header.
    Returns None if the header is absent or the token is invalid (permissive —
    callers decide how to handle None).
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    raw_token = auth_header[len("Bearer "):]
    try:
        payload = jwt.decode(raw_token, settings.secret_key, algorithms=[_JWT_ALGORITHM])
    except jwt.InvalidTokenError:
        return None

    teacher_id = int(payload.get("sub", 0))
    result = await db.execute(select(Teacher).where(Teacher.id == teacher_id))
    return result.scalars().first()


# ---------------------------------------------------------------------------
# List & Create Sessions
# ---------------------------------------------------------------------------

@router.get("", response_model=List[SessionResponse])
async def list_sessions(request: Request, db: AsyncSession = Depends(get_db)):
    """
    List sessions.
    - Admin teachers → all sessions returned.
    - Regular teachers → only sessions where teacher_id matches their own ID.
    """
    teacher = await _get_teacher_from_request(request, db)

    if teacher and not teacher.is_admin:
        # Filter to this teacher's own sessions only
        result = await db.execute(
            select(SessionModel)
            .where(SessionModel.teacher_id == teacher.id)
            .order_by(SessionModel.scheduled_start.desc())
        )
        sessions = result.scalars().all()
        return sessions

    # Admin or unauthenticated (legacy) — return all
    sessions = await crud.list_sessions(db)
    return sessions


@router.post("", response_model=SessionResponse, status_code=201)
async def create_session(body: SessionCreate, request: Request, db: AsyncSession = Depends(get_db)):
    """Create a new monitoring session. Stamps teacher_id from the caller's JWT."""
    teacher = await _get_teacher_from_request(request, db)
    teacher_id: Optional[int] = teacher.id if teacher else None

    session = await crud.create_session(
        db,
        subject_name=body.subject_name,
        scheduled_start=body.scheduled_start,
        scheduled_end=body.scheduled_end,
        teacher_name=body.teacher_name,
        class_div=body.class_div,
        room_no=body.room_no,
        teacher_id=teacher_id,
    )
    pipeline_state.set_session(str(session.session_id))
    pipeline_state.set_class_div(body.class_div)
    logger.info(
        "Session created: %s — %s (Div %s) by teacher_id=%s",
        session.session_id, session.subject_name, session.class_div, teacher_id,
    )
    return session





@router.get("/active", response_model=Optional[SessionResponse])
async def get_active_session(db: AsyncSession = Depends(get_db)):
    """Get the currently active session (is_active=True)."""
    session = await crud.get_active_session(db)
    # Return None instead of 404 so the frontend doesn't show an error banner
    return session


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """Get a specific session by ID."""
    session = await crud.get_session_by_id(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


# ---------------------------------------------------------------------------
# Pause & Resume
# ---------------------------------------------------------------------------

@router.patch("/{session_id}/pause", status_code=200)
async def pause_session(
    session_id: str,
    body: PauseRequest = PauseRequest(),
    db: AsyncSession = Depends(get_db),
):
    """
    Pause a session — logs a SessionIntermission start timestamp.
    Vision pipeline will exclude these frames from A_avg.
    """
    session = await crud.get_session_by_id(db, session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    intermission = await crud.start_intermission(
        db, session_id=session_id, trigger_type=body.trigger_type
    )
    pipeline_state.set_paused(True)
    logger.info("Session %s PAUSED (%s)", session_id[:8], body.trigger_type)
    return {
        "message": "Session paused",
        "intermission_id": intermission.id,
        "started_at": intermission.start_timestamp.isoformat(),
    }


@router.patch("/{session_id}/resume", response_model=ResumeResponse)
async def resume_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """Resume a paused session — closes the open intermission record."""
    session = await crud.get_session_by_id(db, session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    await crud.end_intermission(db, session_id=session_id)
    pipeline_state.set_paused(False)
    now = datetime.now(timezone.utc).isoformat()
    logger.info("Session %s RESUMED", session_id[:8])
    return ResumeResponse(
        session_id=session_id,
        resumed_at=now,
        message="Session resumed successfully",
    )


# ---------------------------------------------------------------------------
# Attention History (for the timeline graph on dashboard)
# ---------------------------------------------------------------------------

@router.get("/{session_id}/attention", response_model=AttentionHistoryResponse)
async def get_attention_history(
    session_id: str,
    roll_no: Optional[int] = Query(None, description="Filter for one student. Omit for class average."),
    limit: int = Query(120, description="Max data points to return (default 120 = 1 hour at 30s intervals)"),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns time-series attention data for the dashboard graph.
    If roll_no provided → individual student's attention over time.
    If omitted → class-wide average attention per minute.
    """
    raw_logs = await crud.get_attention_logs(
        db, session_id=session_id, roll_no=roll_no, limit=limit
    )

    points = [
        AttentionPoint(
            timestamp=log.timestamp.isoformat(),
            attention_avg=round(log.instantaneous_score, 3),
            face_count=1,
        )
        for log in raw_logs
    ]

    return AttentionHistoryResponse(
        session_id=session_id,
        roll_no=roll_no,
        points=points,
    )


# ---------------------------------------------------------------------------
# Q&A Interactions
# ---------------------------------------------------------------------------

@router.get("/{session_id}/qa", response_model=List[QAInteractionResponse])
async def get_qa_interactions(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """List all Q&A interactions for a session."""
    interactions = await crud.get_qa_interactions(db, session_id=session_id)
    return [
        QAInteractionResponse(
            interaction_id=i.interaction_id,
            roll_no=i.roll_no,
            question_text=getattr(i, "question_text", None),
            student_responded=i.student_responded,
            teacher_interrupted=i.teacher_interrupted,
            qa_score=i.qa_score or 0.0,
            score_reason=getattr(i, "score_reason", None),
        )
        for i in interactions
    ]


# ---------------------------------------------------------------------------
# Session Scores — Full student score table for Analytics page
# ---------------------------------------------------------------------------

@router.get("/{session_id}/scores")
async def get_session_scores(session_id: str, db: AsyncSession = Depends(get_db)):
    from db.models import VisualAttentionLog
    from sqlalchemy import select, func

    session = await crud.get_session_by_id(db, session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    result = await db.execute(
        select(VisualAttentionLog.roll_no).distinct().where(
            VisualAttentionLog.session_id == session_id
        )
    )
    roll_numbers = sorted([r for (r,) in result.fetchall()])

    scores = []
    for roll_no in roll_numbers:
        try:
            score_data = await crud.calculate_student_final_score(db, session_id, roll_no)
            student = await crud.get_student_by_roll(db, roll_no)
            score_data["name"] = student.name if student else f"Roll {roll_no}"
            scores.append(score_data)
        except Exception as exc:
            logger.warning("Score calc failed for roll %d: %s", roll_no, exc)

    return {
        "session_id": session_id,
        "subject_name": session.subject_name,
        "scheduled_start": session.scheduled_start.isoformat(),
        "student_count": len(scores),
        "scores": scores,
    }

@router.patch("/{session_id}/end", response_model=SessionResponse)
async def end_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """End an active session."""
    session = await crud.end_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    # Reset pipeline state
    pipeline_state.set_session("")
    return session

@router.get("/{session_id}/attendance")
async def get_session_attendance(session_id: str, db: AsyncSession = Depends(get_db)):
    """
    Returns attendance list for a session.
    Combines all students in the session's class_div with their attendance status.
    """
    from db.models import AttendanceRecord, Student
    from sqlalchemy import select
    
    session = await crud.get_session_by_id(db, session_id)
    if not session:
        raise HTTPException(404, 'Session not found')
    
    # Get all attendance records for this session
    att_result = await db.execute(
        select(AttendanceRecord).where(AttendanceRecord.session_id == session_id)
    )
    att_records = {r.roll_no: r for r in att_result.scalars().all()}
    
    # Get all students in this division
    std_result = await db.execute(
        select(Student).where(Student.class_div == session.class_div).order_by(Student.roll_no)
    )
    students = std_result.scalars().all()
    
    result = []
    for s in students:
        rec = att_records.get(s.roll_no)
        result.append({
            'roll_no': s.roll_no,
            'name': s.name,
            'status': rec.status if rec else 'Absent',
            'punctuality_score': rec.punctuality_score if rec else 0.0,
            'entry_timestamp': rec.entry_timestamp.isoformat() if rec and rec.entry_timestamp else None,
        })
    
    return result
