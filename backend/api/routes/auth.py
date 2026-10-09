"""
backend/api/routes/auth.py
==========================
Authentication routes for teachers.

POST /api/auth/login  → validate credentials, return signed JWT + profile
GET  /api/auth/me     → decode JWT from Authorization header, return teacher profile
"""

import hashlib
import logging
from datetime import datetime, timezone, timedelta

import jwt
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from db.session import get_db
from db.models import Teacher

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Auth"])

# ── JWT helpers ────────────────────────────────────────────────────────────────

_JWT_ALGORITHM = "HS256"
_JWT_EXPIRE_HOURS = 24


def _create_token(teacher: Teacher) -> str:
    """Create a signed JWT for the given teacher."""
    payload = {
        "sub": str(teacher.id),
        "username": teacher.username,
        "is_admin": teacher.is_admin,
        "exp": datetime.now(timezone.utc) + timedelta(hours=_JWT_EXPIRE_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=_JWT_ALGORITHM)


def _decode_token(token: str) -> dict:
    """Decode and validate a JWT. Raises HTTPException on failure."""
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[_JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired")
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {exc}")


def _extract_bearer(request: Request) -> str:
    """Pull the Bearer token from the Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing or not Bearer",
        )
    return auth_header[len("Bearer "):]


# ── Pydantic schemas ───────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    name: str
    username: str
    is_admin: bool
    subject: str | None = None
    division: str | None = None


class MeResponse(BaseModel):
    id: int
    name: str
    username: str
    is_admin: bool
    subject: str | None = None
    division: str | None = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Validate credentials and return a signed JWT plus teacher profile."""
    pwd_hash = hashlib.sha256(req.password.encode()).hexdigest()
    result = await db.execute(
        select(Teacher).where(
            Teacher.username == req.username,
            Teacher.password_hash == pwd_hash,
        )
    )
    teacher = result.scalars().first()
    if not teacher:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    token = _create_token(teacher)
    logger.info("Login successful for teacher '%s' (id=%d)", teacher.username, teacher.id)
    return LoginResponse(
        token=token,
        name=teacher.name,
        username=teacher.username,
        is_admin=teacher.is_admin,
        subject=teacher.subject,
        division=teacher.division,
    )


@router.get("/me", response_model=MeResponse)
async def get_me(request: Request, db: AsyncSession = Depends(get_db)):
    """Return the authenticated teacher's profile from the JWT."""
    raw_token = _extract_bearer(request)
    payload = _decode_token(raw_token)

    teacher_id = int(payload["sub"])
    result = await db.execute(select(Teacher).where(Teacher.id == teacher_id))
    teacher = result.scalars().first()
    if not teacher:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found")

    return MeResponse(
        id=teacher.id,
        name=teacher.name,
        username=teacher.username,
        is_admin=teacher.is_admin,
        subject=teacher.subject,
        division=teacher.division,
    )
