"""
backend/tests/test_db.py
========================
Unit tests for Database Models, CRUD operations, Mathematical Formulas,
and edge-case filtering (Formula 1, Formula 2, Formula 3, Intermission exclusion).
"""

import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from db.session import Base
from db.crud import (
    create_student,
    get_student_by_roll,
    search_students,
    create_session,
    record_attendance,
    calculate_punctuality_score,
    compute_instantaneous_attention,
    log_visual_attention,
    log_qa_interaction,
    start_intermission,
    end_intermission,
    calculate_student_final_score,
)

# Use in-memory SQLite for superfast isolated tests
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

@pytest_asyncio.fixture
async def async_db():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async_session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    async with async_session() as session:
        yield session
        
    await engine.dispose()


# ---------------------------------------------------------------------------
# Test Formula 1: Instantaneous Visual Score A_i(t)
# ---------------------------------------------------------------------------
def test_formula_1_instantaneous_score():
    # A_i(t) = 0.30*H + 0.50*G + 0.20*P
    # Perfect score: H=1.0, G=1.0, P=1.0 -> 1.0
    score = compute_instantaneous_attention(1.0, 1.0, 1.0)
    assert score == 1.0

    # Looking away: H=0.0, G=0.2, P=1.0 -> 0.30*0 + 0.50*0.2 + 0.20*1.0 = 0.10 + 0.20 = 0.30
    score = compute_instantaneous_attention(0.0, 0.2, 1.0)
    assert score == 0.30


# ---------------------------------------------------------------------------
# Test Formula 2: Punctuality Score S_punctual
# ---------------------------------------------------------------------------
def test_formula_2_punctuality():
    start = datetime(2026, 1, 1, 10, 0, 0)
    end = datetime(2026, 1, 1, 11, 0, 0) # 60 mins total

    # On-time entry (10:00) -> 100%
    punc, status = calculate_punctuality_score(start, end, start)
    assert punc == 100.0
    assert status == "On-Time"

    # Halfway entry (10:30) -> 30/60 = 50%
    entry_half = start + timedelta(minutes=30)
    punc_half, status_half = calculate_punctuality_score(start, end, entry_half)
    assert punc_half == 50.0
    assert status_half == "Late"


# ---------------------------------------------------------------------------
# Test Student & Session DB Operations
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_student_and_session_crud(async_db: AsyncSession):
    # 1. Create Student
    student = await create_student(async_db, roll_no=5, name="Avdhoot Kulkarni", class_div="A")
    assert student.roll_no == 5
    assert student.name == "Avdhoot Kulkarni"

    # 2. Retrieve Student
    fetched = await get_student_by_roll(async_db, 5)
    assert fetched is not None
    assert fetched.name == "Avdhoot Kulkarni"

    # 3. Search Student
    results = await search_students(async_db, "Avdhoot")
    assert len(results) == 1
    assert results[0].roll_no == 5

    # 4. Create Session
    now = datetime.utcnow()
    session = await create_session(
        async_db,
        subject_name="Physics 101",
        scheduled_start=now,
        scheduled_end=now + timedelta(hours=1),
    )
    assert session.is_active is True
    assert session.subject_name == "Physics 101"


# ---------------------------------------------------------------------------
# Test Formula 3 & Edge Case 2 (Intermission Exclusion)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_final_multimodal_score_with_intermission(async_db: AsyncSession):
    now = datetime.utcnow()
    session_start = now - timedelta(minutes=30)
    session_end = now + timedelta(minutes=30)

    # 1. Setup Student & Session
    student = await create_student(async_db, roll_no=14, name="Krushna Shinde")
    session = await create_session(
        async_db,
        subject_name="Mathematics",
        scheduled_start=session_start,
        scheduled_end=session_end,
    )

    # 2. Record On-Time Attendance (Punctuality = 100%)
    await record_attendance(async_db, session.session_id, student.roll_no, entry_timestamp=session_start)

    # 3. Log 10 Attention frames before intermission (Score = 1.0)
    for i in range(10):
        t = session_start + timedelta(minutes=i)
        await log_visual_attention(
            async_db,
            session_id=session.session_id,
            roll_no=student.roll_no,
            head_pose_score=1.0,
            eye_gaze_score=1.0,
            posture_score=1.0,
            timestamp=t,
        )

    # 4. Teacher gets a phone call -> Start Intermission at min 15 to min 20
    inter_start = session_start + timedelta(minutes=15)
    inter_end = session_start + timedelta(minutes=20)
    intermission = await start_intermission(
        async_db,
        session_id=session.session_id,
        trigger_type="AUTO_COLLECTIVE_ANOMALY",
        start_timestamp=inter_start,
    )
    await end_intermission(async_db, intermission.id, end_timestamp=inter_end)

    # 5. Log 5 distraction frames during intermission (Score = 0.0)
    # THESE FRAMES MUST BE IGNORED IN THE FINAL SCORE
    for i in range(16, 20):
        t = session_start + timedelta(minutes=i)
        await log_visual_attention(
            async_db,
            session_id=session.session_id,
            roll_no=student.roll_no,
            head_pose_score=0.0,
            eye_gaze_score=0.0,
            posture_score=0.0,
            timestamp=t,
        )

    # 6. QA Interaction: Teacher asks question, student answers (Q_i = 1.0)
    await log_qa_interaction(
        async_db,
        session_id=session.session_id,
        roll_no=student.roll_no,
        student_responded=True,
    )

    # 7. Calculate Final Multimodal Score
    stats = await calculate_student_final_score(async_db, session.session_id, student.roll_no)

    # Formula 3: 0.20*(100/100) + 0.70*(1.0) + 0.10*(1.0) = 0.20 + 0.70 + 0.10 = 1.0 (100%)
    assert stats["punctuality_score"] == 100.0
    assert stats["attention_avg"] == 100.0  # Proves 0.0 intermission frames were excluded!
    assert stats["intermission_frames_excluded"] == 4
    assert stats["final_multimodal_score"] == 100.0
