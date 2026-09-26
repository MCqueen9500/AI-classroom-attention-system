"""
scripts/run_full_pipeline.py
==============================
INTEGRATION SCRIPT — Connects Phase 1 + Phase 2 + Phase 3.

Flow:
  1. Opens webcam (HAL - Phase 1)
  2. Finds or creates an active session (DB - Phase 2)
  3. Runs vision AI pipeline per frame (Vision - Phase 3)
  4. Writes A_i(t) scores to database every second (DB - Phase 2)
  5. Shows live annotated window (Vision - Phase 3)

Controls:
  Q → Quit
  P → Pause / Resume
  S → Print current DB-saved scores to terminal

Usage:
    python scripts/run_full_pipeline.py
    python scripts/run_full_pipeline.py --no-window   (headless, DB only)
"""

import sys, os, time, argparse, asyncio, threading, logging
from datetime import datetime

# ── Path setup ────────────────────────────────────────────────────────────────
ROOT    = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND = os.path.join(ROOT, "backend")
sys.path.insert(0, BACKEND)
sys.path.insert(0, ROOT)

import cv2

# ── Internal imports ──────────────────────────────────────────────────────────
from hal.video_source import WebcamVideoSource, MockVideoSource
from hal.manager      import VideoSourceManager

from pipelines.vision.face_detector       import build_face_detector
from pipelines.vision.landmark_extractor  import LandmarkExtractor
from pipelines.vision.head_pose           import HeadPoseScorer
from pipelines.vision.ear_scorer          import EARScorer
from pipelines.vision.posture_scorer      import PostureScorer
from pipelines.vision.overlay             import draw_frame_overlay
from pipelines.vision.face_recognizer     import FaceRecognizer

from db.session import init_db, AsyncSessionLocal
from db.crud    import (
    compute_instantaneous_attention,
    get_active_session,
    create_session,
    log_visual_attention,
    list_students,
)
from core.config         import settings
from core.logging_config import setup_logging

setup_logging()
logger = logging.getLogger("full_pipeline")


# ─────────────────────────────────────────────────────────────────────────────
# Async DB helpers (run in a separate event loop thread)
# ─────────────────────────────────────────────────────────────────────────────
_db_loop   = asyncio.new_event_loop()
_db_thread = threading.Thread(target=_db_loop.run_forever, daemon=True, name="DBLoop")
_db_thread.start()


def run_async(coro):
    """Run an async coroutine from a sync thread."""
    future = asyncio.run_coroutine_threadsafe(coro, _db_loop)
    return future.result(timeout=10)


async def get_or_create_session():
    async with AsyncSessionLocal() as db:
        session = await get_active_session(db)
        if session:
            logger.info("Found active session: %s (%s)", session.session_id, session.subject_name)
            return session.session_id
        # Create a demo session valid for 2 hours
        from datetime import timedelta
        session = await create_session(
            db,
            subject_name="Live Demo Session",
            scheduled_start=datetime.utcnow(),
            scheduled_end=datetime.utcnow() + timedelta(hours=2),
        )
        logger.info("Created new session: %s", session.session_id)
        return session.session_id


async def write_attention_log(session_id, roll_no, h_i, g_i, p_i, confidence):
    """Write one frame's attention scores to the database."""
    async with AsyncSessionLocal() as db:
        await log_visual_attention(
            db=db,
            session_id=session_id,
            roll_no=roll_no,
            head_pose_score=h_i,
            eye_gaze_score=g_i,
            posture_score=p_i,
            confidence=confidence,
            timestamp=datetime.utcnow(),
        )


async def fetch_student_embeddings():
    """Fetch all registered face embeddings from DB."""
    async with AsyncSessionLocal() as db:
        students = await list_students(db, limit=100)
        embeddings = {}
        for s in students:
            if s.face_embedding is not None:
                import numpy as np
                embeddings[s.roll_no] = np.array(s.face_embedding, dtype=np.float32)
        return embeddings

# ─────────────────────────────────────────────────────────────────────────────
# Main pipeline
# ─────────────────────────────────────────────────────────────────────────────
def run(use_mock=False, show_window=True):

    # ── Step 1: Initialize DB ────────────────────────────────────────────────
    logger.info("Step 1/4 — Initializing database tables...")
    run_async(init_db())

    # ── Step 2: Get active session ───────────────────────────────────────────
    logger.info("Step 2/4 — Getting active session from DB...")
    session_id = run_async(get_or_create_session())

    # Get student roll numbers to assign faces to
    known_rolls = run_async(fetch_student_rolls(limit=30))
    logger.info("Loaded %d known students from DB", len(known_rolls))

    # ── Step 3: Start HAL video source ───────────────────────────────────────
    logger.info("Step 3/4 — Starting video source (HAL)...")
    source = (
        MockVideoSource(total_frames=-1, fps=15.0)
        if use_mock
        else WebcamVideoSource(
            device_index=settings.webcam_device_index,
            target_fps=settings.webcam_fps,
            width=settings.webcam_width,
            height=settings.webcam_height,
        )
    )
    video_mgr = VideoSourceManager(source)
    if not video_mgr.start():
        logger.error("Failed to open video source. Run: python scripts/hal_smoke_test.py")
        sys.exit(1)

    # ── Step 4: Load AI models ───────────────────────────────────────────────
    logger.info("Step 4/4 — Loading AI vision models...")
    detector  = build_face_detector(prefer="mediapipe", min_detection_confidence=0.5)
    extractor = LandmarkExtractor()
    hp_scorer = HeadPoseScorer()
    recognizer = FaceRecognizer()

    # Load embeddings from DB
    known_embeddings = run_async(fetch_student_embeddings())
    logger.info("Loaded %d registered face embeddings from DB", len(known_embeddings))

    # Per-face scorer state (indexed by face position slot)
    ear_scorers  = {}
    post_scorers = {}

    # ── Runtime state ────────────────────────────────────────────────────────
    paused           = False
    frame_count      = 0
    db_write_counter = 0          # write to DB every N frames
    DB_WRITE_EVERY   = 15         # ~1 write/second at 15 FPS
    last_fps_time    = time.time()

    logger.info("=" * 55)
    logger.info("  ALL SYSTEMS CONNECTED — PIPELINE RUNNING")
    logger.info("  Session ID : %s", session_id)
    logger.info("  Press Q=Quit  P=Pause  S=Show DB stats")
    logger.info("=" * 55)

    try:
        while True:
            # ── Grab frame from HAL ──────────────────────────────────────────
            frame_data = video_mgr.get_frame(timeout=0.2)
            if frame_data is None:
                continue

            bgr = frame_data.image
            fh, fw = bgr.shape[:2]
            frame_count += 1

            if paused:
                if show_window:
                    display = bgr.copy()
                    cv2.putText(display, "PAUSED — Press P to resume",
                                (fw//2 - 180, fh//2),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 60, 255), 2)
                    cv2.imshow("Classroom Monitor — LIVE", display)
                key = cv2.waitKey(30) & 0xFF
                if key == ord("q"): break
                if key == ord("p"): paused = False
                continue

            # ── PHASE 3: Detect faces + score each one ───────────────────────
            detections  = detector.detect(bgr)
            face_results = []

            for idx, det in enumerate(detections):
                x, y, bw, bh = det.bbox

                # Lazy-create per-face scorers
                if idx not in ear_scorers:
                    ear_scorers[idx]  = EARScorer()
                    post_scorers[idx] = PostureScorer()

                # Extract landmarks
                landmarks = extractor.extract(det.face_crop, crop_x=x, crop_y=y)
                if landmarks is None:
                    continue

                # Compute H_i, G_i, P_i, A_i
                yaw, pitch, roll, h_i = hp_scorer.compute(landmarks, fw, fh)
                ear, g_i, is_drowsy   = ear_scorers[idx].compute(landmarks)
                p_i                   = post_scorers[idx].compute(landmarks, fh, roll)
                a_i                   = compute_instantaneous_attention(h_i, g_i, p_i)
                confidence            = round((det.confidence + landmarks.confidence) / 2, 3)

                # ── Phase 7: Real Face Recognition ───────────────────────────
                roll_no = None
                if hasattr(det, 'yunet_face_row'):
                    emb = recognizer.extract_embedding(bgr, det.yunet_face_row)
                    match_roll = recognizer.match(emb, known_embeddings, threshold=0.4)
                    if match_roll is not None:
                        roll_no = match_roll
                
                # Fallback to unknown if not recognized
                if roll_no is None:
                    # Give them a temporary negative ID so they still track without polluting DB
                    roll_no = -(idx + 1)

                # ── PHASE 2: Write to DB every DB_WRITE_EVERY frames ─────────
                if frame_count % DB_WRITE_EVERY == 0:
                    try:
                        run_async(write_attention_log(
                            session_id=session_id,
                            roll_no=roll_no,
                            h_i=h_i, g_i=g_i, p_i=p_i,
                            confidence=confidence,
                        ))
                        db_write_counter += 1
                    except Exception as e:
                        logger.warning("DB write failed: %s", e)

                face_results.append({
                    "bbox": det.bbox,
                    "h_i": h_i, "g_i": g_i, "p_i": p_i, "a_i": a_i,
                    "ear": ear, "is_drowsy": is_drowsy,
                    "yaw": yaw, "pitch": pitch, "roll": roll,
                    "landmarks_px": landmarks.landmarks_px,
                    "roll_no": roll_no,
                })

            # ── Class-level attention % ──────────────────────────────────────
            class_pct = (
                sum(r["a_i"] for r in face_results) / len(face_results) * 100.0
                if face_results else 0.0
            )

            # ── Push to Dashboard ────────────────────────────────────────────
            if frame_count % 7 == 0:
                def push_dashboard():
                    try:
                        import requests
                        payload = {
                            "session_id": str(session_id),
                            "class_attention_pct": float(class_pct),
                            "faces": []
                        }
                        for r in face_results:
                            payload["faces"].append({
                                "roll_no": int(r["roll_no"]),
                                "slot": int(r.get("slot", 0)),
                                "h_i": float(r["h_i"]),
                                "g_i": float(r["g_i"]),
                                "p_i": float(r["p_i"]),
                                "a_i": float(r["a_i"]),
                                "is_drowsy": bool(r["is_drowsy"]),
                                "is_speaking": bool(r.get("is_speaking", False)),
                                "confidence": float(r.get("confidence", 0.9)),
                                "bbox": [int(x) for x in r["bbox"]]
                            })
                        requests.post("http://localhost:8000/api/telemetry/vision", json=payload, timeout=0.5)
                    except:
                        pass
                threading.Thread(target=push_dashboard, daemon=True).start()

            # ── PHASE 3: Draw overlay ────────────────────────────────────────
            if show_window:
                annotated = draw_frame_overlay(bgr, face_results, class_pct, paused)

                # FPS counter
                elapsed = time.time() - last_fps_time
                fps = frame_count / elapsed if elapsed > 0 else 0
                cv2.putText(annotated, f"FPS:{fps:.1f}  DB writes:{db_write_counter}",
                            (fw - 200, 20), cv2.FONT_HERSHEY_SIMPLEX,
                            0.45, (200, 200, 200), 1)

                cv2.imshow("Classroom Monitor — LIVE", annotated)

            # ── Key controls ─────────────────────────────────────────────────
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            elif key == ord("p"):
                paused = not paused
                logger.info("Pipeline %s", "PAUSED" if paused else "RESUMED")
            elif key == ord("s"):
                # Print live stats to terminal
                print(f"\n{'='*60}")
                print(f"  LIVE DB STATS  |  Session: {session_id[:8]}...")
                print(f"  Frames processed : {frame_count}")
                print(f"  DB writes done   : {db_write_counter}")
                print(f"  Faces this frame : {len(face_results)}")
                print(f"  Class attention  : {class_pct:.1f}%")
                for r in face_results:
                    print(f"  Roll {r['roll_no']:>3}: "
                          f"H={r['h_i']:.2f} G={r['g_i']:.2f} "
                          f"P={r['p_i']:.2f} A={r['a_i']:.2f} "
                          f"{'DROWSY' if r['is_drowsy'] else ''}")
                print(f"{'='*60}\n")

    finally:
        video_mgr.stop()
        detector.close()
        extractor.close()
        if show_window:
            cv2.destroyAllWindows()
        logger.info("Pipeline stopped. Total frames: %d | DB writes: %d",
                    frame_count, db_write_counter)


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Full Integrated Pipeline (Phase 1+2+3)")
    parser.add_argument("--source",    choices=["webcam", "mock"], default="webcam")
    parser.add_argument("--no-window", action="store_true", help="Run headless (no cv2 window)")
    args = parser.parse_args()

    run(
        use_mock=   (args.source == "mock"),
        show_window=(not args.no_window),
    )
