"""
backend/db/models.py
====================
SQLAlchemy models matching the classroom attention monitoring requirements:
1. students
2. sessions
3. attendance_records
4. visual_attention_logs (Time-series)
5. qa_interactions
6. session_intermissions
"""

import uuid
from datetime import datetime
from typing import Optional, Any
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    Index,
)
from sqlalchemy.orm import relationship
from .session import Base


# ---------------------------------------------------------------------------
# 0. Teachers Table (Authentication)
# ---------------------------------------------------------------------------
class Teacher(Base):
    __tablename__ = "teachers"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(100), nullable=False)
    name = Column(String(100), nullable=False)


# ---------------------------------------------------------------------------
# 1. Students Table
# ---------------------------------------------------------------------------
class Student(Base):
    __tablename__ = "students"

    roll_no = Column(Integer, primary_key=True, index=True, autoincrement=False)
    name = Column(String(100), nullable=False, index=True)
    class_div = Column(String(20), nullable=False, default="A")
    face_embedding = Column(JSON, nullable=True)  # 512-d or 128-d vector stored as JSON array

    # Relationships
    attendance_records = relationship("AttendanceRecord", back_populates="student", cascade="all, delete-orphan")
    attention_logs = relationship("VisualAttentionLog", back_populates="student", cascade="all, delete-orphan")
    qa_interactions = relationship("QAInteraction", back_populates="student", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Student(roll_no={self.roll_no}, name='{self.name}', class_div='{self.class_div}')>"


# ---------------------------------------------------------------------------
# 2. Sessions Table
# ---------------------------------------------------------------------------
class Session(Base):
    __tablename__ = "sessions"

    session_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    subject_name = Column(String(100), nullable=False)
    scheduled_start = Column(DateTime, nullable=False, default=datetime.utcnow)
    scheduled_end = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    attendance_records = relationship("AttendanceRecord", back_populates="session", cascade="all, delete-orphan")
    attention_logs = relationship("VisualAttentionLog", back_populates="session", cascade="all, delete-orphan")
    qa_interactions = relationship("QAInteraction", back_populates="session", cascade="all, delete-orphan")
    intermissions = relationship("SessionIntermission", back_populates="session", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Session(id='{self.session_id}', subject='{self.subject_name}', active={self.is_active})>"


# ---------------------------------------------------------------------------
# 3. Attendance Records Table
# ---------------------------------------------------------------------------
class AttendanceRecord(Base):
    __tablename__ = "attendance_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False, index=True)
    roll_no = Column(Integer, ForeignKey("students.roll_no", ondelete="CASCADE"), nullable=False, index=True)
    entry_timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    punctuality_score = Column(Float, nullable=False, default=100.0)  # Percentage S_punctual
    status = Column(String(20), nullable=False, default="On-Time")    # 'On-Time', 'Late', 'Absent'

    session = relationship("Session", back_populates="attendance_records")
    student = relationship("Student", back_populates="attendance_records")

    __table_args__ = (
        Index("idx_attendance_session_student", "session_id", "roll_no", unique=True),
    )


# ---------------------------------------------------------------------------
# 4. Visual Attention Logs (Time-Series)
# ---------------------------------------------------------------------------
class VisualAttentionLog(Base):
    __tablename__ = "visual_attention_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    session_id = Column(String(36), ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False, index=True)
    roll_no = Column(Integer, ForeignKey("students.roll_no", ondelete="CASCADE"), nullable=False, index=True)
    
    # Mathematical Sub-Components (0.0 to 1.0)
    head_pose_score = Column(Float, nullable=False)        # H_i
    eye_gaze_score = Column(Float, nullable=False)         # G_i (EAR-based)
    posture_score = Column(Float, nullable=False)          # P_i
    instantaneous_score = Column(Float, nullable=False)    # A_i(t) = 0.3*H + 0.5*G + 0.2*P
    confidence = Column(Float, nullable=False, default=1.0) # Vision pipeline tracking confidence (0.0 - 1.0)

    session = relationship("Session", back_populates="attention_logs")
    student = relationship("Student", back_populates="attention_logs")

    __table_args__ = (
        Index("idx_attention_session_roll_time", "session_id", "roll_no", "timestamp"),
    )


# ---------------------------------------------------------------------------
# 5. QA Interactions Table
# ---------------------------------------------------------------------------
class QAInteraction(Base):
    __tablename__ = "qa_interactions"

    interaction_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False, index=True)
    roll_no = Column(Integer, ForeignKey("students.roll_no", ondelete="CASCADE"), nullable=False, index=True)
    question_timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    teacher_interrupted = Column(Boolean, nullable=False, default=False)
    student_responded = Column(Boolean, nullable=False, default=False)
    qa_score = Column(Float, nullable=False, default=1.0)  # Q_i: 1.0 = responded/interrupted safeguard, 0.0 = no response in 15s

    session = relationship("Session", back_populates="qa_interactions")
    student = relationship("Student", back_populates="qa_interactions")


# ---------------------------------------------------------------------------
# 6. Session Intermissions Table
# ---------------------------------------------------------------------------
class SessionIntermission(Base):
    __tablename__ = "session_intermissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False, index=True)
    start_timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    end_timestamp = Column(DateTime, nullable=True)  # NULL until intermission ends
    trigger_type = Column(String(50), nullable=False)  # 'AUTO_COLLECTIVE_ANOMALY', 'MANUAL_TEACHER_PAUSE'

    session = relationship("Session", back_populates="intermissions")
