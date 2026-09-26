"""
backend/api/routes/sessions.py
================================
REST endpoints for session management.

GET    /api/sessions            → list all sessions
POST   /api/sessions            → create new session
GET    /api/sessions/{id}       → get session detail
PATCH  /api/sessions/{id}/pause  → pause (log intermission)
PATCH  /api/sessions/{id}/resume → resume session
GET    /api/sessions/{id}/attention → attention time-series (for graph)
GET    /api/sessions/{id}/qa    → list all Q&A interactions
"""

import logging
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from db import crud
from api.schemas import (
    SessionCreate, SessionResponse,
    AttentionHistoryResponse, AttentionPoint,
    QAInteractionResponse, PauseRequest, ResumeResponse,
)
from api.pipeline_state import pipeline_state

logger  = logging.getLogger(__name__)
router  = APIRouter(prefix="/api/sessions", tags=["Sessions"])


# ---------------------------------------------------------------------------
# List & Create Sessions
# ---------------------------------------------------------------------------

@router.get("", response_model=List[SessionResponse])
async def list_sessions(db: AsyncSession = Depends(get_db)):
    """List all sessions (most recent first)."""
    sessions = await crud.list_sessions(db)
    return sessions


@router.post("", response_model=SessionResponse, status_code=201)
async def create_session(body: SessionCreate, db: AsyncSession = Depends(get_db)):
    """Create a new monitoring session."""
    session = await crud.create_session(
        db,
        subject_name=body.subject_name,
        scheduled_start=body.scheduled_start,
        scheduled_end=body.scheduled_end,
    )
    pipeline_state.set_session(str(session.session_id))
    logger.info("Session created: %s — %s", session.session_id, session.subject_name)
    return session


@router.get("/active", response_model=Optional[SessionResponse])
async def get_active_session(db: AsyncSession = Depends(get_db)):
    """Get the currently active session (is_active=True)."""
    session = await crud.get_active_session(db)
    if not session:
        raise HTTPException(status_code=404, detail="No active session found")
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
            attention_avg=round(log.attention_score or log.head_pose_score, 3),
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
            interaction_id=i.id,
            roll_no=i.roll_no,
            question_text=getattr(i, "question_text", None),
            student_responded=i.student_responded,
            teacher_interrupted=i.teacher_interrupted,
            qa_score=i.qa_score or 0.0,
            score_reason=getattr(i, "score_reason", None),
        )
        for i in interactions
    ]
