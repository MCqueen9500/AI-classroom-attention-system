"""
scripts/seed_db.py
==================
Populates the database with 30 sample students and an active classroom session.
Also generates synthetic attention logs and Q&A interactions for immediate testing.

Usage:
    python scripts/seed_db.py
"""

import sys
import os
import asyncio
from datetime import datetime, timedelta

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from db.session import init_db, AsyncSessionLocal
from db.crud import (
    create_student,
    create_session,
    record_attendance,
    log_visual_attention,
    log_qa_interaction,
    calculate_student_final_score,
)

SAMPLE_STUDENTS = [
    (1, "Aarav Sharma", "A"),
    (2, "Aditi Patel", "A"),
    (3, "Akash Verma", "A"),
    (4, "Ananya Iyer", "A"),
    (5, "Avdhoot Kulkarni", "A"),
    (6, "Bhavna Joshi", "A"),
    (7, "Chirag Mehta", "A"),
    (8, "Deepak Rao", "A"),
    (9, "Divya Deshmukh", "A"),
    (10, "Gaurav Singh", "A"),
    (11, "Harshita Nair", "A"),
    (12, "Ishaan Reddy", "A"),
    (13, "Kavya Menon", "A"),
    (14, "Krushna Shinde", "A"),
    (15, "Manish Gupta", "A"),
    (16, "Neha Bhatt", "A"),
    (17, "Nikhil Patil", "A"),
    (18, "Pooja Hegde", "A"),
    (19, "Pranav Saxena", "A"),
    (20, "Priya Nair", "A"),
    (21, "Rahul Deshpande", "A"),
    (22, "Rohan Kumar", "A"),
    (23, "Sakshi Sawant", "A"),
    (24, "Sameer Khan", "A"),
    (25, "Siddharth Sen", "A"),
    (26, "Sneha Kadam", "A"),
    (27, "Tanvi More", "A"),
    (28, "Varun Kapoor", "A"),
    (29, "Vedant Joshi", "A"),
    (30, "Zoya Akhtar", "A"),
]


async def seed():
    print("[1/4] Initializing database tables...")
    await init_db()

    async with AsyncSessionLocal() as db:
        from db.models import Teacher
        import hashlib
        pwd_hash = hashlib.sha256("password".encode()).hexdigest()
        teacher = Teacher(username="admin", password_hash=pwd_hash, name="Dr. Admin")
        db.add(teacher)
        await db.commit()

        print("[2/4] Seeding 30 students...")
        for roll_no, name, div in SAMPLE_STUDENTS:
            try:
                await create_student(db, roll_no=roll_no, name=name, class_div=div)
            except Exception:
                # If already seeded, proceed
                pass

        print("[3/4] Creating active classroom session (Computer Vision & AI - CS301)...")
        now = datetime.utcnow()
        session = await create_session(
            db,
            subject_name="Computer Vision & AI - CS301",
            scheduled_start=now - timedelta(minutes=20),
            scheduled_end=now + timedelta(minutes=40),
        )

        print("[4/4] Generating initial attendance & attention telemetry for demo...")
        # Record attendance for first 25 students (Roll 1-25 On-Time, 26-28 Late, 29-30 Absent)
        for roll, _, _ in SAMPLE_STUDENTS[:25]:
            await record_attendance(
                db, session.session_id, roll, entry_timestamp=session.scheduled_start
            )
        for roll, _, _ in SAMPLE_STUDENTS[25:28]:
            await record_attendance(
                db, session.session_id, roll, entry_timestamp=session.scheduled_start + timedelta(minutes=10)
            )

        # Log simulated attention data for Roll 5 (Avdhoot) and Roll 14 (Krushna)
        for r in [5, 14, 21, 27]:
            for minute_offset in range(15):
                t = session.scheduled_start + timedelta(minutes=minute_offset)
                await log_visual_attention(
                    db=db,
                    session_id=session.session_id,
                    roll_no=r,
                    head_pose_score=0.92,
                    eye_gaze_score=0.88,
                    posture_score=0.95,
                    confidence=0.98,
                    timestamp=t,
                )

        # Simulate a Q&A interaction for Roll 27 (Tanvi More)
        await log_qa_interaction(
            db=db,
            session_id=session.session_id,
            roll_no=27,
            student_responded=True,
            teacher_interrupted=False,
        )

        # Test calculation for Roll 14
        score_data = await calculate_student_final_score(db, session.session_id, 14)
        print("\n" + "=" * 55)
        print("          DATABASE SEEDING SUCCESSFUL!")
        print("=" * 55)
        print(f"  Session ID           : {session.session_id}")
        print(f"  Subject              : {session.subject_name}")
        print(f"  Sample Student Roll  : {score_data['roll_no']}")
        print(f"  Attendance Status    : {score_data['attendance_status']}")
        print(f"  Punctuality Score    : {score_data['punctuality_score']}%")
        print(f"  Visual Attention Avg : {score_data['attention_avg']}%")
        print(f"  Final Multimodal %   : {score_data['final_multimodal_score']}%")
        print("=" * 55)


if __name__ == "__main__":
    asyncio.run(seed())
