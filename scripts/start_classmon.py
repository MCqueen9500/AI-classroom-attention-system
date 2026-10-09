"""
scripts/start_classmon.py
===========================
REPAIR 5A — Edge-only launcher for the Audio pipeline.

The API server is now managed separately via run_server.py.
Run it first in a dedicated terminal:

    python run_server.py          ← Terminal 1 (API server)
    python scripts/start_classmon.py  ← Terminal 2 (Audio edge pipeline)

This script:
  1. Reads CLASSMON_API_URL from the environment (default: http://localhost:8000)
  2. Health-checks the API (up to 10 retries, 2s apart) before proceeding
  3. Launches the Audio Pipeline on the main thread

Usage:
  cd classroom-attention-monitor
  .venv\\Scripts\\activate
  python scripts/start_classmon.py
"""

import sys, os, time, logging, requests

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))
sys.path.insert(0, ROOT)

from core.logging_config import setup_logging
from core.config import settings
from api.pipeline_state import pipeline_state

setup_logging()
logger = logging.getLogger("startup")

# ---------------------------------------------------------------------------
# REPAIR 5A: Cloud/Edge separation — API base URL from environment
# ---------------------------------------------------------------------------
API_BASE = os.getenv("CLASSMON_API_URL", "http://localhost:8000")

print("TIP: Run 'python run_server.py' in a SEPARATE terminal first.")

# ---------------------------------------------------------------------------
# Health check: wait for the API to become reachable
# ---------------------------------------------------------------------------
def wait_for_api(base_url: str, retries: int = 10, delay: float = 2.0) -> bool:
    """
    Poll GET /health up to *retries* times with *delay* seconds between attempts.
    Returns True if reachable, False otherwise.
    """
    health_url = f"{base_url}/health"
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(health_url, timeout=3)
            if r.status_code == 200:
                logger.info("API is reachable at %s (attempt %d/%d)", base_url, attempt, retries)
                return True
        except Exception:
            pass
        logger.warning(
            "API not reachable yet at %s — attempt %d/%d. Retrying in %.0fs...",
            base_url, attempt, retries, delay,
        )
        time.sleep(delay)
    return False

# ---------------------------------------------------------------------------
# Worker: Audio Pipeline
# ---------------------------------------------------------------------------
def start_audio():
    from pipelines.audio.audio_pipeline import AudioPipeline
    from db.session import AsyncSessionLocal
    import asyncio

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

    logger.info("Starting Audio Pipeline (api_base_url=%s)...", API_BASE)
    from hal.manager import AudioSourceManager
    from hal.audio_source import MicrophoneAudioSource
    audio_mgr = AudioSourceManager(source=MicrophoneAudioSource())
    audio_mgr.start()  # BUG FIX: Actually start the microphone thread!
    
    audio = AudioPipeline(audio_manager=audio_mgr, session_id=session_id, api_base_url=API_BASE)
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
    print("  ClassMon Audio Edge Pipeline")
    print(f"  API base: {API_BASE}")
    print("=" * 60)

    # Verify API is up before doing anything
    if not wait_for_api(API_BASE):
        print(
            f"\nERROR: ClassMon API not reachable at {API_BASE} after 10 attempts.\n"
            "Make sure 'python run_server.py' is running in another terminal.\n"
        )
        sys.exit(1)

    try:
        print("\nPress Ctrl+C to stop.\n")
        start_audio()
    except KeyboardInterrupt:
        print("\nShutting down...")
