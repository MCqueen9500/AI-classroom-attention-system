"""
scripts/start_classmon.py
===========================
Master start script for the Classroom Attention Monitor.

This script boots everything in one go:
  1. FastAPI Server (REST + WebSocket) on port 8000
  2. Vision Pipeline (Webcam face tracking)
  3. Audio Pipeline (Microphone Q&A tracking)

Usage:
  cd classroom-attention-monitor
  .venv\Scripts\activate
  python scripts/start_classmon.py
"""

import sys, os, time, threading, logging, uvicorn

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))
sys.path.insert(0, ROOT)

from core.logging_config import setup_logging
from core.config import settings
from api.pipeline_state import pipeline_state

setup_logging()
logger = logging.getLogger("startup")

# ---------------------------------------------------------------------------
# Worker 1: FastAPI Server
# ---------------------------------------------------------------------------
def start_api():
    logger.info("Starting FastAPI server on %s:%s...", settings.api_host, settings.api_port)
    uvicorn.run(
        "api.app:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
        log_level=settings.log_level.lower(),
        app_dir=os.path.join(ROOT, "backend"),
    )

# ---------------------------------------------------------------------------
# Worker 2: Audio Pipeline
# ---------------------------------------------------------------------------
def start_audio():
    # Only import if needed to save time
    from pipelines.audio.audio_pipeline import AudioPipeline
    from db.session import AsyncSessionLocal
    import asyncio
    
    # Needs session_id from DB
    from db.crud import get_active_session, create_session
    from datetime import datetime, timedelta

    async def get_or_create_session():
        async with AsyncSessionLocal() as db:
            s = await get_active_session(db)
            if s: return s.session_id
            s = await create_session(db, "Live Session", datetime.utcnow(), datetime.utcnow() + timedelta(hours=2))
            return s.session_id

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    session_id = loop.run_until_complete(get_or_create_session())
    pipeline_state.set_session(session_id)
    
    logger.info("Starting Audio Pipeline...")
    audio = AudioPipeline(session_id=session_id)
    audio.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        audio.stop()

# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 60)
    print("  🚀 Starting ClassMon Multi-modal System")
    print("=" * 60)
    
    # Note: Vision pipeline isn't integrated yet into this launcher,
    # as it requires main thread for OpenCV cv2.imshow
    # The user can just run scripts/run_server.py and scripts/run_full_pipeline.py separately for now.

    # Start API in background thread
    api_thread = threading.Thread(target=start_api, daemon=True)
    api_thread.start()
    
    # Wait for API to boot
    time.sleep(2)
    
    try:
        print("\nPress Ctrl+C to stop.\n")
        start_audio()
    except KeyboardInterrupt:
        print("\nShutting down...")
