"""
backend/api/routes/auth.py
==========================
Simple authentication route for teachers.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
import hashlib

from db.session import get_db
from db.models import Teacher

router = APIRouter(prefix="/api/auth", tags=["Auth"])

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    token: str
    name: str

@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    pwd_hash = hashlib.sha256(req.password.encode()).hexdigest()
    result = await db.execute(
        select(Teacher).where(Teacher.username == req.username, Teacher.password_hash == pwd_hash)
    )
    teacher = result.scalars().first()
    if not teacher:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    # In a real app, generate a JWT. For demo, just return a dummy token.
    return {"token": f"token-{teacher.id}", "name": teacher.name}
