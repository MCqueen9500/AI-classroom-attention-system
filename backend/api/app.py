"""
backend/api/app.py
====================
Main FastAPI application factory.

Startup lifecycle:
  1. Create DB tables (if not exist)
  2. Run SQLite ALTER TABLE migrations for new columns (idempotent)
  3. Seed default admin account (is_admin=True)
  4. Start WebSocket broadcast loop (asyncio background task)

All routes are registered here:
  GET/POST  /api/sessions/...   → session management
  GET       /api/students/...   → student data + scores
  WS        /ws/{session_id}    → live telemetry stream
  GET/POST  /api/admin/...      → admin-only management endpoints

CORS is open to localhost:3000 (React dashboard) and localhost:5173 (Vite dev).
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.logging_config import setup_logging
from core.config import settings
from db.session import engine, Base
from api.routes import sessions, students, websocket
from api.broadcaster import broadcast_loop

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan handler — runs on startup and shutdown.
    Startup:  create DB tables, run column migrations, seed admin, start WS loop
    Shutdown: cancel broadcast loop cleanly
    """
    # ── Startup ────────────────────────────────────────────────────────
    logger.info("Starting up ClassMon API server...")

    # Create all DB tables if they don't exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    db_path = settings.database_url.replace("sqlite+aiosqlite:///", "").replace("./", "")
    logger.info("DB ready at: %s - all tables verified.", db_path)

    # ── SQLite column migrations (idempotent via PRAGMA table_info) ────
    import sqlite3
    if os.path.exists(db_path):
        try:
            conn_sq = sqlite3.connect(db_path)
            cur = conn_sq.cursor()

            # --- teachers table ---
            existing_teachers = [
                row[1] for row in cur.execute("PRAGMA table_info(teachers)").fetchall()
            ]
            if "is_admin" not in existing_teachers:
                cur.execute(
                    "ALTER TABLE teachers ADD COLUMN is_admin BOOLEAN DEFAULT 0 NOT NULL"
                )
                logger.info("Migration: added teachers.is_admin")
            if "subject" not in existing_teachers:
                cur.execute("ALTER TABLE teachers ADD COLUMN subject VARCHAR(100)")
                logger.info("Migration: added teachers.subject")
            if "division" not in existing_teachers:
                cur.execute("ALTER TABLE teachers ADD COLUMN division VARCHAR(10)")
                logger.info("Migration: added teachers.division")

            # --- sessions table ---
            existing_sessions = [
                row[1] for row in cur.execute("PRAGMA table_info(sessions)").fetchall()
            ]
            if "teacher_id" not in existing_sessions:
                cur.execute(
                    "ALTER TABLE sessions ADD COLUMN teacher_id INTEGER REFERENCES teachers(id)"
                )
                logger.info("Migration: added sessions.teacher_id")

            # --- qa_interactions table ---
            existing_qa = [
                row[1] for row in cur.execute("PRAGMA table_info(qa_interactions)").fetchall()
            ]
            if "question_text" not in existing_qa:
                cur.execute("ALTER TABLE qa_interactions ADD COLUMN question_text VARCHAR(500)")
                logger.info("Migration: added qa_interactions.question_text")
            if "student_response_text" not in existing_qa:
                cur.execute("ALTER TABLE qa_interactions ADD COLUMN student_response_text VARCHAR(1000)")
                logger.info("Migration: added qa_interactions.student_response_text")
            if "llm_feedback" not in existing_qa:
                cur.execute("ALTER TABLE qa_interactions ADD COLUMN llm_feedback VARCHAR(500)")
                logger.info("Migration: added qa_interactions.llm_feedback")

            # --- visual_attention_logs ---
            existing_val = [
                row[1] for row in cur.execute("PRAGMA table_info(visual_attention_logs)").fetchall()
            ]
            if "mar" not in existing_val:
                cur.execute("ALTER TABLE visual_attention_logs ADD COLUMN mar FLOAT")
                logger.info("Migration: added visual_attention_logs.mar")

            conn_sq.commit()
            conn_sq.close()
            logger.info("SQLite column migrations applied successfully.")
        except Exception as mig_exc:
            logger.error("SQLite migration error: %s", mig_exc)

    # ── Upsert default admin (create OR ensure is_admin=True) ──────────
    from db.session import AsyncSessionLocal
    from db.models import Teacher
    from sqlalchemy import select
    import hashlib

    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Teacher).where(Teacher.username == 'admin'))
        admin = res.scalars().first()
        if admin:
            admin.is_admin = True
            await db.commit()
            logger.info("Admin account updated: is_admin=True")
        else:
            pwd_hash = hashlib.sha256('password'.encode()).hexdigest()
            admin = Teacher(username='admin', password_hash=pwd_hash, name='Dr. Admin', is_admin=True)
            db.add(admin)
            await db.commit()
            logger.info("Created default admin user (admin/password).")

    # ── Launch WebSocket broadcast background task ─────────────────────
    broadcast_task = asyncio.create_task(broadcast_loop())
    logger.info("WebSocket broadcast loop started.")

    # ── Launch auto session-end watcher (checks every 30s) ────────────
    async def auto_end_sessions():
        """Background task: ends sessions whose scheduled_end has passed."""
        from db.session import AsyncSessionLocal
        from db.models import Session as SessionModel
        from sqlalchemy import select
        from datetime import datetime, timezone

        while True:
            await asyncio.sleep(30)
            try:
                async with AsyncSessionLocal() as db:
                    now = datetime.utcnow()
                    result = await db.execute(
                        select(SessionModel).where(
                            SessionModel.is_active == True,
                            SessionModel.scheduled_end <= now,
                        )
                    )
                    expired = result.scalars().all()
                    for session in expired:
                        session.is_active = False
                        logger.info(
                            "AUTO-END: Session %s (%s) ended at scheduled time %s",
                            str(session.session_id)[:8],
                            session.subject_name,
                            session.scheduled_end.isoformat(),
                        )
                    if expired:
                        await db.commit()
                        # Reset live pipeline state so dashboard shows idle
                        from api.pipeline_state import pipeline_state
                        pipeline_state.set_session("")
            except Exception as exc:
                logger.warning("auto_end_sessions error: %s", exc)

    auto_end_task = asyncio.create_task(auto_end_sessions())
    logger.info("Auto session-end watcher started (checks every 30s).")

    yield   # ← server is running here

    # ── Shutdown ────────────────────────────────────────────────────────
    broadcast_task.cancel()
    auto_end_task.cancel()
    try:
        await broadcast_task
    except asyncio.CancelledError:
        pass
    try:
        await auto_end_task
    except asyncio.CancelledError:
        pass
    logger.info("ClassMon API server shut down cleanly.")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Classroom Attention Monitor API",
        description=(
            "Real-time multimodal student engagement tracking. "
            "Vision + Audio + LLM Q&A scoring with live WebSocket streaming."
        ),
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS — allow React dashboard (dev and prod)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",   # React CRA
            "http://localhost:5173",   # Vite
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from api.routes import telemetry, auth, admin

    # ── REST Routes ────────────────────────────────────────────────────
    app.include_router(auth.router)
    app.include_router(admin.router)
    app.include_router(sessions.router)
    app.include_router(students.router)
    app.include_router(telemetry.router)

    # ── WebSocket Route ────────────────────────────────────────────────
    app.include_router(websocket.router)

    # ── Health check ───────────────────────────────────────────────────
    @app.get("/health", tags=["Health"])
    async def health():
        return {"status": "ok", "service": "classmon-api"}

    # ── Serve React Frontend (Deployment) ──────────────────────────────
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse

    frontend_dist = os.path.join(os.path.dirname(__file__), "..", "..", "dashboard", "dist")
    if os.path.exists(frontend_dist):
        app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")

        # Fallback for React Router (SPA)
        @app.get("/{catchall:path}", include_in_schema=False)
        async def serve_spa(catchall: str):
            from fastapi import HTTPException
            if catchall.startswith("api/") or catchall.startswith("docs") or catchall.startswith("ws"):
                raise HTTPException(status_code=404, detail="Not found")
            return FileResponse(os.path.join(frontend_dist, "index.html"))

    return app


app = create_app()
