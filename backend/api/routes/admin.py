"""
backend/api/routes/admin.py
============================
Admin-only REST endpoints.  All routes require a valid JWT where
teacher.is_admin == True, enforced by the `require_admin` dependency.

GET    /api/admin/teachers          → list all teacher accounts
POST   /api/admin/teachers          → create a new teacher account
DELETE /api/admin/teachers/{id}     → delete a teacher account
GET    /api/admin/stats             → school-wide aggregate stats
GET    /api/admin/stats/divisions   → per-division attention averages
"""

import hashlib
import logging
from typing import List, Optional

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from db.session import get_db
from db.models import Teacher, Session, Student, VisualAttentionLog

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["Admin"])

_JWT_ALGORITHM = "HS256"


# ── Auth helper ───────────────────────────────────────────────────────────────

async def require_admin(request: Request, db: AsyncSession = Depends(get_db)) -> Teacher:
    """
    Dependency that decodes the Bearer JWT and asserts the caller is an admin.
    Raises 401 if the token is missing/invalid, 403 if the caller is not admin.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing or not Bearer",
        )
    raw_token = auth_header[len("Bearer "):]

    try:
        payload = jwt.decode(raw_token, settings.secret_key, algorithms=[_JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired")
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {exc}")

    teacher_id = int(payload.get("sub", 0))
    result = await db.execute(select(Teacher).where(Teacher.id == teacher_id))
    teacher = result.scalars().first()
    if not teacher:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Teacher not found")
    if not teacher.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return teacher


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class TeacherOut(BaseModel):
    id: int
    username: str
    name: str
    is_admin: bool
    subject: Optional[str] = None
    division: Optional[str] = None

    class Config:
        from_attributes = True


class TeacherCreate(BaseModel):
    username: str
    password: str
    name: str
    subject: Optional[str] = None
    division: Optional[str] = None
    is_admin: bool = False


class StatsOut(BaseModel):
    total_sessions: int
    total_students: int
    avg_attention: Optional[float]
    active_sessions: int
    teacher_count: int


class DivisionStatsOut(BaseModel):
    division: str
    avg_attention: Optional[float]
    session_count: int


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/teachers", response_model=List[TeacherOut])
async def list_teachers(
    db: AsyncSession = Depends(get_db),
    _admin: Teacher = Depends(require_admin),
):
    """List all teacher accounts (admin only)."""
    result = await db.execute(select(Teacher).order_by(Teacher.id))
    teachers = result.scalars().all()
    return teachers


@router.post("/teachers", response_model=TeacherOut, status_code=201)
async def create_teacher(
    body: TeacherCreate,
    db: AsyncSession = Depends(get_db),
    _admin: Teacher = Depends(require_admin),
):
    """Create a new teacher account (admin only). Returns 409 if username already taken."""
    # Conflict check
    existing = await db.execute(select(Teacher).where(Teacher.username == body.username))
    if existing.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{body.username}' already exists",
        )

    pwd_hash = hashlib.sha256(body.password.encode()).hexdigest()
    teacher = Teacher(
        username=body.username,
        password_hash=pwd_hash,
        name=body.name,
        subject=body.subject,
        division=body.division,
        is_admin=body.is_admin,
    )
    db.add(teacher)
    await db.commit()
    await db.refresh(teacher)
    logger.info(
        "Admin created teacher '%s' (id=%d, is_admin=%s)",
        teacher.username, teacher.id, teacher.is_admin,
    )
    return teacher


@router.delete("/teachers/{teacher_id}", status_code=204)
async def delete_teacher(
    teacher_id: int,
    db: AsyncSession = Depends(get_db),
    admin: Teacher = Depends(require_admin),
):
    """Delete a teacher account (admin only). Cannot delete yourself."""
    if teacher_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account",
        )

    result = await db.execute(select(Teacher).where(Teacher.id == teacher_id))
    teacher = result.scalars().first()
    if not teacher:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found")

    await db.delete(teacher)
    await db.commit()
    logger.info("Admin deleted teacher id=%d ('%s')", teacher_id, teacher.username)
    # 204 No Content — return nothing


@router.get("/stats", response_model=StatsOut)
async def get_stats(
    db: AsyncSession = Depends(get_db),
    _admin: Teacher = Depends(require_admin),
):
    """Return school-wide aggregate statistics (admin only)."""
    total_sessions_row = await db.execute(select(func.count()).select_from(Session))
    total_sessions: int = total_sessions_row.scalar() or 0

    total_students_row = await db.execute(select(func.count()).select_from(Student))
    total_students: int = total_students_row.scalar() or 0

    avg_attention_row = await db.execute(
        select(func.avg(VisualAttentionLog.instantaneous_score)).select_from(VisualAttentionLog)
    )
    avg_attention_raw = avg_attention_row.scalar()
    avg_attention: Optional[float] = round(float(avg_attention_raw), 4) if avg_attention_raw is not None else None

    active_sessions_row = await db.execute(
        select(func.count()).select_from(Session).where(Session.is_active == True)  # noqa: E712
    )
    active_sessions: int = active_sessions_row.scalar() or 0

    teacher_count_row = await db.execute(select(func.count()).select_from(Teacher))
    teacher_count: int = teacher_count_row.scalar() or 0

    return StatsOut(
        total_sessions=total_sessions,
        total_students=total_students,
        avg_attention=avg_attention,
        active_sessions=active_sessions,
        teacher_count=teacher_count,
    )


@router.get("/stats/divisions", response_model=List[DivisionStatsOut])
async def get_division_stats(
    db: AsyncSession = Depends(get_db),
    _admin: Teacher = Depends(require_admin),
):
    """
    Per-division attention averages grouped by sessions.class_div (admin only).
    Returns [{division, avg_attention, session_count}] sorted alphabetically.
    """
    # Join VisualAttentionLog → Session on session_id, group by class_div
    stmt = (
        select(
            Session.class_div,
            func.avg(VisualAttentionLog.instantaneous_score).label("avg_attention"),
            func.count(distinct(Session.session_id)).label("session_count"),
        )
        .join(VisualAttentionLog, VisualAttentionLog.session_id == Session.session_id, isouter=True)
        .group_by(Session.class_div)
        .order_by(Session.class_div)
    )
    result = await db.execute(stmt)
    rows = result.fetchall()

    divisions: List[DivisionStatsOut] = []
    for row in rows:
        class_div, avg_att, session_count = row
        divisions.append(
            DivisionStatsOut(
                division=class_div or "Unknown",
                avg_attention=round(float(avg_att), 4) if avg_att is not None else None,
                session_count=session_count or 0,
            )
        )
    return divisions
