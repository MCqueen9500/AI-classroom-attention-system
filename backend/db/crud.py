"""
backend/db/crud.py
==================
Async CRUD and aggregation helpers for the Attention Monitoring System.
Includes implementations of the core scoring and edge-case formulas.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, and_, desc

from .models import (
    Student,
    Session,
    AttendanceRecord,
    VisualAttentionLog,
    QAInteraction,
    SessionIntermission,
)
from core.config import settings


# ---------------------------------------------------------------------------
# Students CRUD
# ---------------------------------------------------------------------------
async def create_student(
    db: AsyncSession,
    roll_no: int,
    name: str,
    class_div: str = "A",
    face_embedding: Optional[List[float]] = None,
) -> Student:
    """Inserts a new student."""
    student = Student(
        roll_no=roll_no,
        name=name,
        class_div=class_div,
        face_embedding=face_embedding,
    )
    db.add(student)
    await db.commit()
    await db.refresh(student)
    return student


async def get_student_by_roll(db: AsyncSession, roll_no: int) -> Optional[Student]:
    """Finds a student by roll number."""
    result = await db.execute(select(Student).where(Student.roll_no == roll_no))
    return result.scalar_one_or_none()


async def search_students(db: AsyncSession, query: str) -> List[Student]:
    """Searches students by name or roll number."""
    if query.isdigit():
        roll = int(query)
        result = await db.execute(
            select(Student).where(
                (Student.roll_no == roll) | (Student.name.ilike(f"%{query}%"))
            )
        )
    else:
        result = await db.execute(
            select(Student).where(Student.name.ilike(f"%{query}%"))
        )
    return list(result.scalars().all())


async def list_students(db: AsyncSession, limit: int = 100) -> List[Student]:
    """Returns a list of registered students."""
    result = await db.execute(select(Student).order_by(Student.roll_no).limit(limit))
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Sessions CRUD
# ---------------------------------------------------------------------------
async def create_session(
    db: AsyncSession,
    subject_name: str,
    scheduled_start: datetime,
    scheduled_end: datetime,
) -> Session:
    """Creates a new classroom lecture session."""
    session = Session(
        subject_name=subject_name,
        scheduled_start=scheduled_start,
        scheduled_end=scheduled_end,
        is_active=True,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def get_active_session(db: AsyncSession) -> Optional[Session]:
    """Retrieves the currently active class session."""
    result = await db.execute(
        select(Session).where(Session.is_active == True).order_by(desc(Session.scheduled_start))
    )
    return result.scalar_one_or_none()


async def end_session(db: AsyncSession, session_id: str) -> Optional[Session]:
    """Marks a session as inactive/completed."""
    result = await db.execute(select(Session).where(Session.session_id == session_id))
    session = result.scalar_one_or_none()
    if session:
        session.is_active = False
        await db.commit()
        await db.refresh(session)
    return session


# ---------------------------------------------------------------------------
# Attendance CRUD & Formula 2
# ---------------------------------------------------------------------------
def calculate_punctuality_score(
    scheduled_start: datetime,
    scheduled_end: datetime,
    entry_timestamp: datetime,
) -> Tuple[float, str]:
    """
    Formula 2: Attendance & Punctuality
    S_punctual = ((T_end - T_entry) / (T_end - T_start)) * 100%
    """
    total_duration = (scheduled_end - scheduled_start).total_seconds()
    if total_duration <= 0:
        return 100.0, "On-Time"

    # If student entered before or right at class start
    if entry_timestamp <= scheduled_start:
        return 100.0, "On-Time"

    # If student entered after class ended
    if entry_timestamp >= scheduled_end:
        return 0.0, "Absent"

    remaining_duration = (scheduled_end - entry_timestamp).total_seconds()
    punctuality = (remaining_duration / total_duration) * 100.0
    punctuality = max(0.0, min(100.0, punctuality))

    # Grace period: within 5 minutes of start is considered On-Time
    late_threshold = scheduled_start + timedelta(minutes=5)
    status = "On-Time" if entry_timestamp <= late_threshold else "Late"

    return round(punctuality, 2), status


async def record_attendance(
    db: AsyncSession,
    session_id: str,
    roll_no: int,
    entry_timestamp: Optional[datetime] = None,
) -> AttendanceRecord:
    """Records student arrival and computes punctuality score."""
    entry_timestamp = entry_timestamp or datetime.utcnow()

    # Fetch session to calculate punctuality
    sess_res = await db.execute(select(Session).where(Session.session_id == session_id))
    session = sess_res.scalar_one_or_none()
    if not session:
        raise ValueError(f"Session '{session_id}' not found")

    punctuality, status = calculate_punctuality_score(
        session.scheduled_start, session.scheduled_end, entry_timestamp
    )

    # Check if record already exists
    existing_res = await db.execute(
        select(AttendanceRecord).where(
            and_(
                AttendanceRecord.session_id == session_id,
                AttendanceRecord.roll_no == roll_no,
            )
        )
    )
    existing = existing_res.scalar_one_or_none()
    if existing:
        return existing

    record = AttendanceRecord(
        session_id=session_id,
        roll_no=roll_no,
        entry_timestamp=entry_timestamp,
        punctuality_score=punctuality,
        status=status,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


# ---------------------------------------------------------------------------
# Visual Attention Logs & Formula 1
# ---------------------------------------------------------------------------
def compute_instantaneous_attention(
    head_pose_score: float,
    eye_gaze_score: float,
    posture_score: float,
    w_h: float = settings.weight_head_pose,
    w_g: float = settings.weight_eye_gaze,
    w_p: float = settings.weight_posture,
) -> float:
    """
    Formula 1: Instantaneous Visual Score
    A_i(t) = (0.30 * H_i) + (0.50 * G_i) + (0.20 * P_i)
    """
    score = (w_h * head_pose_score) + (w_g * eye_gaze_score) + (w_p * posture_score)
    return round(max(0.0, min(1.0, score)), 4)


async def log_visual_attention(
    db: AsyncSession,
    session_id: str,
    roll_no: int,
    head_pose_score: float,
    eye_gaze_score: float,
    posture_score: float,
    confidence: float = 1.0,
    timestamp: Optional[datetime] = None,
) -> VisualAttentionLog:
    """Logs a single time-series attention frame measurement."""
    instantaneous_score = compute_instantaneous_attention(
        head_pose_score=head_pose_score,
        eye_gaze_score=eye_gaze_score,
        posture_score=posture_score,
    )

    log_entry = VisualAttentionLog(
        timestamp=timestamp or datetime.utcnow(),
        session_id=session_id,
        roll_no=roll_no,
        head_pose_score=head_pose_score,
        eye_gaze_score=eye_gaze_score,
        posture_score=posture_score,
        instantaneous_score=instantaneous_score,
        confidence=confidence,
    )
    db.add(log_entry)
    await db.commit()
    await db.refresh(log_entry)
    return log_entry


# ---------------------------------------------------------------------------
# QA Interactions CRUD (Edge Case 1)
# ---------------------------------------------------------------------------
async def log_qa_interaction(
    db: AsyncSession,
    session_id: str,
    roll_no: int,
    student_responded: bool,
    teacher_interrupted: bool = False,
    question_timestamp: Optional[datetime] = None,
) -> QAInteraction:
    """
    Logs Q&A interaction.
    Teacher Interruption Safeguard:
    If teacher interrupted or student responded, Q_i = 1.0 (no penalty).
    If student failed to respond in window, Q_i = 0.0.
    """
    if teacher_interrupted or student_responded:
        qa_score = 1.0
    else:
        qa_score = 0.0

    interaction = QAInteraction(
        session_id=session_id,
        roll_no=roll_no,
        question_timestamp=question_timestamp or datetime.utcnow(),
        teacher_interrupted=teacher_interrupted,
        student_responded=student_responded,
        qa_score=qa_score,
    )
    db.add(interaction)
    await db.commit()
    await db.refresh(interaction)
    return interaction


# ---------------------------------------------------------------------------
# Session Intermissions (Edge Case 2)
# ---------------------------------------------------------------------------
async def start_intermission(
    db: AsyncSession,
    session_id: str,
    trigger_type: str,
    start_timestamp: Optional[datetime] = None,
) -> SessionIntermission:
    """Starts an intermission period (pausing attention tracking calculations)."""
    intermission = SessionIntermission(
        session_id=session_id,
        start_timestamp=start_timestamp or datetime.utcnow(),
        trigger_type=trigger_type,
    )
    db.add(intermission)
    await db.commit()
    await db.refresh(intermission)
    return intermission


async def end_intermission(
    db: AsyncSession,
    intermission_id: int,
    end_timestamp: Optional[datetime] = None,
) -> Optional[SessionIntermission]:
    """Ends an intermission period."""
    result = await db.execute(
        select(SessionIntermission).where(SessionIntermission.id == intermission_id)
    )
    intermission = result.scalar_one_or_none()
    if intermission:
        intermission.end_timestamp = end_timestamp or datetime.utcnow()
        await db.commit()
        await db.refresh(intermission)
    return intermission


# ---------------------------------------------------------------------------
# Multimodal Final Score Calculation (Formula 3 & Edge Case 2 Intermission Filter)
# ---------------------------------------------------------------------------
async def calculate_student_final_score(
    db: AsyncSession,
    session_id: str,
    roll_no: int,
) -> Dict[str, Any]:
    """
    Formula 3: Final Multimodal Score (%)
    Individual Score % = (0.20 * (S_punctual / 100) + 0.70 * A_avg + 0.10 * Q_i) * 100%

    Edge-Case 2 Rule:
    Excludes all attention frames captured during intermission periods
    from the denominator and numerator of A_avg.
    """
    # 1. Attendance & Punctuality
    att_res = await db.execute(
        select(AttendanceRecord).where(
            and_(
                AttendanceRecord.session_id == session_id,
                AttendanceRecord.roll_no == roll_no,
            )
        )
    )
    attendance = att_res.scalar_one_or_none()
    punctuality_score = attendance.punctuality_score if attendance else 0.0
    attendance_status = attendance.status if attendance else "Absent"

    # 2. Intermission Ranges
    inter_res = await db.execute(
        select(SessionIntermission).where(SessionIntermission.session_id == session_id)
    )
    intermissions = inter_res.scalars().all()

    # 3. Fetch Visual Attention Logs
    logs_res = await db.execute(
        select(VisualAttentionLog).where(
            and_(
                VisualAttentionLog.session_id == session_id,
                VisualAttentionLog.roll_no == roll_no,
            )
        )
    )
    all_logs = logs_res.scalars().all()

    # Filter out frames captured during intermissions
    valid_logs = []
    for log in all_logs:
        in_intermission = False
        for inter in intermissions:
            end_time = inter.end_timestamp or datetime.utcnow()
            if inter.start_timestamp <= log.timestamp <= end_time:
                in_intermission = True
                break
        if not in_intermission:
            valid_logs.append(log)

    if valid_logs:
        a_avg = sum(l.instantaneous_score for l in valid_logs) / len(valid_logs)
        avg_head = sum(l.head_pose_score for l in valid_logs) / len(valid_logs)
        avg_eye = sum(l.eye_gaze_score for l in valid_logs) / len(valid_logs)
        avg_posture = sum(l.posture_score for l in valid_logs) / len(valid_logs)
        avg_confidence = sum(l.confidence for l in valid_logs) / len(valid_logs)
    else:
        a_avg = 0.0
        avg_head = 0.0
        avg_eye = 0.0
        avg_posture = 0.0
        avg_confidence = 0.0

    # 4. Q&A Average Score
    qa_res = await db.execute(
        select(QAInteraction).where(
            and_(
                QAInteraction.session_id == session_id,
                QAInteraction.roll_no == roll_no,
            )
        )
    )
    qa_list = qa_res.scalars().all()
    q_avg = (sum(q.qa_score for q in qa_list) / len(qa_list)) if qa_list else 1.0

    # 5. Formula 3 Final Multimodal Combination
    w_punc = settings.weight_punctuality
    w_att = settings.weight_attention_avg
    w_qa = settings.weight_qa

    final_pct = (
        (w_punc * (punctuality_score / 100.0))
        + (w_att * a_avg)
        + (w_qa * q_avg)
    ) * 100.0
    final_pct = round(max(0.0, min(100.0, final_pct)), 2)

    # Uncertainty / Low-Confidence Flag
    requires_review = avg_confidence < settings.low_confidence_threshold if valid_logs else False

    return {
        "roll_no": roll_no,
        "session_id": session_id,
        "attendance_status": attendance_status,
        "punctuality_score": punctuality_score,
        "attention_avg": round(a_avg * 100.0, 2),
        "head_alignment_avg": round(avg_head * 100.0, 2),
        "eye_openness_avg": round(avg_eye * 100.0, 2),
        "posture_avg": round(avg_posture * 100.0, 2),
        "qa_score": round(q_avg * 100.0, 2),
        "final_multimodal_score": final_pct,
        "total_frames_analyzed": len(valid_logs),
        "intermission_frames_excluded": len(all_logs) - len(valid_logs),
        "confidence": round(avg_confidence, 2),
        "requires_review": requires_review,
    }


# ---------------------------------------------------------------------------
# Phase 5 API helpers
# ---------------------------------------------------------------------------

async def get_student(db, roll_no):
    return await get_student_by_roll(db, roll_no=roll_no)

async def get_session_by_id(db, session_id):
    from sqlalchemy import select
    from .models import Session
    result = await db.execute(select(Session).where(Session.session_id == session_id))
    return result.scalar_one_or_none()

async def list_sessions(db, limit=50):
    from sqlalchemy import select, desc
    from .models import Session
    result = await db.execute(select(Session).order_by(desc(Session.scheduled_start)).limit(limit))
    return list(result.scalars().all())

async def get_attention_logs(db, session_id, roll_no=None, limit=120):
    from sqlalchemy import select
    from .models import VisualAttentionLog
    q = select(VisualAttentionLog).where(VisualAttentionLog.session_id == session_id)
    if roll_no is not None:
        q = q.where(VisualAttentionLog.roll_no == roll_no)
    q = q.order_by(VisualAttentionLog.timestamp.asc()).limit(limit)
    result = await db.execute(q)
    return list(result.scalars().all())

async def get_qa_interactions(db, session_id):
    from sqlalchemy import select
    from .models import QAInteraction
    result = await db.execute(
        select(QAInteraction).where(QAInteraction.session_id == session_id)
        .order_by(QAInteraction.question_timestamp.asc())
    )
    return list(result.scalars().all())
