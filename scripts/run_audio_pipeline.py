"""
scripts/run_audio_pipeline.py
==============================
Standalone Audio Q&A Pipeline — runs separately from the vision pipeline.

Flow:
  Microphone → VAD → Whisper → RollDetector → QA Window → Ollama/Keyword Score
  → POST /api/telemetry/audio  (updates dashboard Q&A panel in real time)
  → POST /api/telemetry/qa_log (writes final Q_i score to DB)

Requires:
  - Backend server running: python scripts/run_server.py
  - An active session already created via the dashboard

Usage:
  python scripts/run_audio_pipeline.py

Speak: "Roll number 14, what is the EAR formula?"
       → Dashboard Q&A panel lights up with 15-second countdown
       → Student answers → Ollama/keyword scores the response
"""

import sys, os, time, logging, asyncio, threading
import requests

ROOT    = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND = os.path.join(ROOT, "backend")
sys.path.insert(0, BACKEND)
sys.path.insert(0, ROOT)

from core.logging_config import setup_logging
from core.config import settings

setup_logging()
logger = logging.getLogger("audio_pipeline")

API_BASE = f"http://localhost:{settings.api_port}/api"


# ── Wait for an active session ────────────────────────────────────────────────
def wait_for_session() -> str:
    logger.info("Waiting for an active session on the dashboard...")
    while True:
        try:
            r = requests.get(f"{API_BASE}/sessions/active", timeout=3)
            if r.status_code == 200:
                data = r.json()
                if data and "session_id" in data:
                    logger.info("Found active session: %s  (%s)",
                                data["session_id"][:8], data.get("subject_name", ""))
                    return data["session_id"]
        except Exception:
            pass
        time.sleep(2)


# ── Fetch student list for name-based roll detection ─────────────────────────
def fetch_students():
    try:
        r = requests.get(f"{API_BASE}/students", timeout=5)
        if r.status_code == 200:
            students = r.json()
            logger.info("Loaded %d students for roll/name detection.", len(students))
            return students
    except Exception as e:
        logger.warning("Could not fetch student list: %s", e)
    return []


# ── Push Q&A result to DB via API ─────────────────────────────────────────────
def push_qa_log(session_id: str, roll_no: int, qa_score: float,
                student_responded: bool, teacher_interrupted: bool,
                question_text: str = ""):
    def _post():
        try:
            requests.post(f"{API_BASE}/telemetry/qa_log", json={
                "session_id": session_id,
                "roll_no": roll_no,
                "question_text": question_text,
                "qa_score": qa_score,
                "student_responded": student_responded,
                "teacher_interrupted": teacher_interrupted,
            }, timeout=3)
            logger.info("QA logged → Roll %d | Q_i=%.2f | responded=%s",
                        roll_no, qa_score, student_responded)
        except Exception as e:
            logger.warning("Failed to log QA: %s", e)
    threading.Thread(target=_post, daemon=True).start()


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    from hal.audio_source import MicrophoneAudioSource
    from hal.manager import AudioSourceManager
    from pipelines.audio.audio_pipeline import AudioPipeline
    from pipelines.audio.qa_window import QAInteractionRecord

    session_id = wait_for_session()
    students   = fetch_students()

    # Callback fired when a Q&A window closes with a final score
    def on_qa_complete(record: QAInteractionRecord):
        # Derive booleans from fields that actually exist on QAInteractionRecord
        teacher_interrupted = record.score_method == "interrupted"
        student_responded   = bool(record.student_answer) or teacher_interrupted

        push_qa_log(
            session_id=session_id,
            roll_no=record.roll_no,
            qa_score=record.Q_i,
            student_responded=student_responded,
            teacher_interrupted=teacher_interrupted,
            question_text=record.question_text or "",
        )

    # Start microphone
    mic_source = MicrophoneAudioSource(
        sample_rate=16000,
        chunk_duration_ms=100,
    )
    audio_mgr = AudioSourceManager(source=mic_source)
    if not audio_mgr.start():
        logger.error("Failed to open microphone. Check system audio settings.")
        sys.exit(1)

    # Build and start pipeline
    pipeline = AudioPipeline(
        audio_manager=audio_mgr,
        session_id=session_id,
        known_students=[{"roll_no": s["roll_no"], "name": s["name"]} for s in students],
        on_qa_complete=on_qa_complete,
    )
    pipeline.start()

    print("=" * 60)
    print("  AUDIO PIPELINE RUNNING")
    print("  Session :", session_id[:8], "...")
    print("  Mic     : listening...")
    print()
    print("  Speak: 'Roll number 14, what is the EAR formula?'")
    print("         'Roll 7, explain head pose estimation'")
    print("         'Krushna, what is yaw angle?'  (name lookup)")
    print()
    print("  Press Ctrl+C to stop.")
    print("=" * 60)

    try:
        while True:
            # Print last transcript every 2s so you can see what Whisper heard
            transcript = pipeline.get_last_transcript()
            if transcript:
                print(f"\r  [Whisper heard]: {transcript[:80]:<80}", end="", flush=True)
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStopping audio pipeline...")
    finally:
        pipeline.stop()
        audio_mgr.stop()
        logger.info("Audio pipeline stopped.")


if __name__ == "__main__":
    main()
