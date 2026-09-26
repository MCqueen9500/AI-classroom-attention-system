"""
backend/api/routes/students.py
================================
REST endpoints for student data.

GET  /api/students               → list all students (with optional search)
GET  /api/students/{roll_no}     → single student profile
GET  /api/students/{roll_no}/score?session_id=... → final multimodal score
GET  /api/students/search?q=...  → search by name or roll number
"""

import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from db import crud
from api.schemas import StudentResponse, StudentScoreResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/students", tags=["Students"])


@router.get("", response_model=List[StudentResponse])
async def list_students(
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List all registered students."""
    students = await crud.list_students(db, limit=limit)
    return students


@router.get("/search", response_model=List[StudentResponse])
async def search_students(
    q: str = Query(..., min_length=1, description="Name or roll number to search"),
    db: AsyncSession = Depends(get_db),
):
    """
    Search students by name (partial match) or exact roll number.
    Used by the dashboard search bar.
    """
    students = await crud.search_students(db, query=q)
    if not students:
        raise HTTPException(404, f"No students found for query: '{q}'")
    return students


@router.get("/{roll_no}", response_model=StudentResponse)
async def get_student(roll_no: int, db: AsyncSession = Depends(get_db)):
    """Get a single student's profile."""
    student = await crud.get_student(db, roll_no=roll_no)
    if not student:
        raise HTTPException(404, f"Student with roll {roll_no} not found")
    return student


@router.get("/{roll_no}/score", response_model=StudentScoreResponse)
async def get_student_score(
    roll_no: int,
    session_id: Optional[str] = Query(None, description="Session ID. Uses active session if omitted."),
    db: AsyncSession = Depends(get_db),
):
    """
    Compute and return the final multimodal engagement score for a student.
    Applies Formula 3: 20% punctuality + 70% attention avg + 10% Q&A.
    Excludes intermission frames automatically.
    """
    student = await crud.get_student(db, roll_no=roll_no)
    if not student:
        raise HTTPException(404, f"Student roll {roll_no} not found")

    # Use active session if not specified
    if not session_id:
        session = await crud.get_active_session(db)
        if not session:
            raise HTTPException(404, "No active session. Pass ?session_id=...")
        session_id = str(session.session_id)

    score_data = await crud.calculate_student_final_score(
        db, session_id=session_id, roll_no=roll_no
    )

    return StudentScoreResponse(
        roll_no=roll_no,
        name=student.name,
        punctuality_score=round(score_data.get("punctuality_score", 0.0), 2),
        attention_avg=round(score_data.get("attention_avg", 0.0), 4),
        qa_score=round(score_data.get("qa_score", 0.0), 3),
        final_score_pct=round(score_data.get("final_score_pct", 0.0), 2),
        total_logs=score_data.get("total_logs", 0),
    )

from pydantic import BaseModel

class StudentCreate(BaseModel):
    roll_no: int
    name: str
    class_div: str = 'A'

@router.post('', response_model=StudentResponse)
async def create_new_student(student: StudentCreate, db: AsyncSession = Depends(get_db)):
    from db.crud import create_student
    from sqlalchemy.exc import IntegrityError
    try:
        new_student = await create_student(db, student.roll_no, student.name, student.class_div)
        return new_student
    except IntegrityError:
        raise HTTPException(status_code=400, detail='Student with this roll number already exists.')

class FaceRegistration(BaseModel):
    image_base64: str

@router.post('/{roll_no}/face')
async def register_student_face(roll_no: int, payload: FaceRegistration, db: AsyncSession = Depends(get_db)):
    from db.crud import get_student
    student = await get_student(db, roll_no)
    if not student:
        raise HTTPException(status_code=404, detail='Student not found')

    import base64
    import numpy as np
    import cv2
    from pipelines.vision.face_detector import build_face_detector
    from pipelines.vision.face_recognizer import FaceRecognizer

    try:
        header, encoded = payload.image_base64.split(',', 1) if ',' in payload.image_base64 else ('', payload.image_base64)
        image_data = base64.b64decode(encoded)
        nparr = np.frombuffer(image_data, np.uint8)
        bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if bgr is None:
            raise ValueError('Invalid image data')
    except Exception as e:
        raise HTTPException(status_code=400, detail=f'Image decoding failed: {e}')

    detector = build_face_detector(prefer='mediapipe', min_detection_confidence=0.5)
    detections = detector.detect(bgr)
    if not detections:
        raise HTTPException(status_code=400, detail='No face detected in the image.')
    if len(detections) > 1:
        raise HTTPException(status_code=400, detail='Multiple faces detected. Please ensure only the student is visible.')
    
    det = detections[0]
    if not hasattr(det, 'yunet_face_row'):
        raise HTTPException(status_code=500, detail='Detector does not support SFace alignment.')

    recognizer = FaceRecognizer()
    embedding = recognizer.extract_embedding(bgr, det.yunet_face_row)
    
    student.face_embedding = embedding.tolist()
    await db.commit()
    return {'status': 'success', 'message': f'Face registered for roll {roll_no}'}

@router.get('/all/embeddings')
async def get_all_embeddings(db: AsyncSession = Depends(get_db)):
    from db.crud import list_students
    students = await list_students(db, limit=1000)
    result = {}
    for s in students:
        if s.face_embedding is not None:
            result[s.roll_no] = s.face_embedding
    return result
