"""
backend/api/app.py
====================
Main FastAPI application factory.

Startup lifecycle:
  1. Create DB tables (if not exist)
  2. Start WebSocket broadcast loop (asyncio background task)

All routes are registered here:
  GET/POST  /api/sessions/...   → session management
  GET       /api/students/...   → student data + scores
  WS        /ws/{session_id}    → live telemetry stream

CORS is open to localhost:3000 (React dashboard) and localhost:5173 (Vite dev).
"""

import asyncio
import logging
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
    Startup:  create DB tables, start WebSocket broadcast loop
    Shutdown: cancel broadcast loop cleanly
    """
    # ── Startup ────────────────────────────────────────────────────────
    logger.info("Starting up ClassMon API server...")

    # Create all DB tables if they don't exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables ready.")

    # Seed default admin if needed
    from db.session import AsyncSessionLocal
    from db.models import Teacher
    from sqlalchemy import select
    import hashlib
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Teacher).limit(1))
        if not res.scalars().first():
            pwd_hash = hashlib.sha256("password".encode()).hexdigest()
            admin = Teacher(username="admin", password_hash=pwd_hash, name="Dr. Admin")
            db.add(admin)
            await db.commit()
            logger.info("Created default admin user (admin/password).")

    # Launch WebSocket broadcast background task
    broadcast_task = asyncio.create_task(broadcast_loop())
    logger.info("WebSocket broadcast loop started.")

    yield   # ← server is running here

    # ── Shutdown ────────────────────────────────────────────────────────
    broadcast_task.cancel()
    try:
        await broadcast_task
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

    from api.routes import telemetry, auth

    # ── REST Routes ────────────────────────────────────────────────────
    app.include_router(auth.router)
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
    import os
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse
    
    frontend_dist = os.path.join(os.path.dirname(__file__), "..", "..", "dashboard", "dist")
    if os.path.exists(frontend_dist):
        app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")
        
        # Fallback for React Router (SPA)
        @app.get("/{catchall:path}", include_in_schema=False)
        async def serve_spa(catchall: str):
            if catchall.startswith("api/") or catchall.startswith("docs") or catchall.startswith("ws"):
                raise HTTPException(status_code=404, detail="Not found")
            return FileResponse(os.path.join(frontend_dist, "index.html"))

    return app


app = create_app()
