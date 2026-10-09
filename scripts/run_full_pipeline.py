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
from pipelines.vision.lip_activity import LipActivityTracker, QASpeakerChecker
import numpy as np

import requests

# REPAIR 5B: Cloud/Edge separation — resolve API base URL from environment
_API_ROOT = os.getenv("CLASSMON_API_URL", "http://localhost:8000")
API_BASE = f"{_API_ROOT}/api"

# We only need the formula from crud now
from db.crud import compute_instantaneous_attention
from core.config         import settings
from core.logging_config import setup_logging

setup_logging()
logger = logging.getLogger("full_pipeline")
logger.info("Full pipeline starting — API_BASE=%s", API_BASE)


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


def get_or_create_session():
    import time
    logger.info("Waiting for an active session to be created on the dashboard...")
    while True:
        try:
            res = requests.get(f"{API_BASE}/sessions/active")
            if res.status_code == 200:
                data = res.json()
                if data and "session_id" in data:
                    logger.info(f"Found active session: {data['session_id']}")
                    return data["session_id"]
        except Exception as e:
            pass
        time.sleep(2.0)

def write_attention_log(session_id, roll_no, h_i, g_i, p_i, confidence, mar=0.0):
    import threading
    def push():
        try:
            requests.post(f"{API_BASE}/telemetry/log", json={
                "session_id": str(session_id),
                "roll_no": int(roll_no),
                "h_i": float(h_i),
                "g_i": float(g_i),
                "p_i": float(p_i),
                "confidence": float(confidence),
                "mar": float(mar)
            }, timeout=1.0)
        except:
            pass
    threading.Thread(target=push, daemon=True).start()

def fetch_student_embeddings():
    import numpy as np
    embeddings = {}
    try:
        res = requests.get(f"{API_BASE}/students/all/embeddings")
        if res.status_code == 200:
            data = res.json()
            for r_str, emb_list in data.items():
                embeddings[int(r_str)] = np.array(emb_list, dtype=np.float32)
    except Exception as e:
        logger.error(f"Failed to fetch embeddings: {e}")
    return embeddings

# ─────────────────────────────────────────────────────────────────────────────
# Main pipeline
# ─────────────────────────────────────────────────────────────────────────────
def run(use_mock=False, show_window=True):

    # ── Step 1: Initialize DB ────────────────────────────────────────────────
    # ── Step 1: Get active session ───────────────────────────────────────────
    logger.info("Step 1/3 — Getting active session from API...")
    session_id = get_or_create_session()
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
    detector  = build_face_detector(prefer="yunet", min_detection_confidence=0.5)
    extractor = LandmarkExtractor()
    hp_scorer = HeadPoseScorer()
    recognizer = FaceRecognizer()
    lip_tracker = LipActivityTracker(window_frames=15, speaking_threshold=0.0003)
    qa_checker = QASpeakerChecker(lip_tracker)

    # Load embeddings from API
    known_embeddings = fetch_student_embeddings()
    logger.info("Loaded %d registered face embeddings from API", len(known_embeddings))

    # Per-face scorer state (indexed by face position slot)
    ear_scorers  = {}
    post_scorers = {}

    # ── Runtime state ────────────────────────────────────────────────────────
    _face_seen_frames: dict = {}
    _attendance_marked: set = set()
    _qa_was_active: bool = False
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
            
            # Refresh embeddings dynamically every 10 seconds so new registrations take effect instantly
            if frame_count % 150 == 0:
                def refresh():
                    new_emb = fetch_student_embeddings()
                    if new_emb:
                        known_embeddings.update(new_emb)
                threading.Thread(target=refresh, daemon=True).start()

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
                
                mar = 0.0
                if landmarks is not None and landmarks.landmarks_px is not None:
                    lip_tracker.update(idx, landmarks.landmarks_px, fh)
                    lm = landmarks.landmarks_px
                    if len(lm) > 291:
                        upper = lm[13].astype(float)
                        lower = lm[14].astype(float)
                        left  = lm[61].astype(float)
                        right = lm[291].astype(float)
                        vert  = float(np.linalg.norm(upper - lower))
                        horiz = float(np.linalg.norm(left - right))
                        mar   = vert / horiz if horiz > 1 else 0.0

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
                elif roll_no > 0:
                    _face_seen_frames[roll_no] = _face_seen_frames.get(roll_no, 0) + 1
                    if roll_no not in _attendance_marked and _face_seen_frames[roll_no] >= 30:
                        _attendance_marked.add(roll_no)
                        def _mark_att(sid, rno):
                            try:
                                requests.post(f"{API_BASE}/telemetry/attendance",
                                    json={"session_id": sid, "roll_no": rno}, timeout=2)
                            except: pass
                        threading.Thread(target=_mark_att, args=(session_id, roll_no), daemon=True).start()
                        logger.info("Attendance marked PRESENT: Roll %d (%d frames seen)", roll_no, _face_seen_frames[roll_no])

                # ── PHASE 2: Write to DB every DB_WRITE_EVERY frames ─────────
                if frame_count % DB_WRITE_EVERY == 0:
                    try:
                        # Pushes asynchronously via requests in a thread, or just block lightly
                        write_attention_log(
                            session_id=session_id,
                            roll_no=roll_no,
                            h_i=h_i, g_i=g_i, p_i=p_i,
                            confidence=confidence,
                            mar=mar
                        )
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
                    "mar": mar,
                })


            # ── Class-level attention % ──────────────────────────────────────
            if frame_count % 15 == 0:
                try:
                    r = requests.get(f"{API_BASE}/sessions/active", timeout=0.3)
                    if r.status_code == 200:
                        qa_state = r.json().get("qa_state", {})
                        if qa_state.get("active"):
                            if not _qa_was_active:
                                qa_checker.start(qa_state.get("asked_roll"))
                                _qa_was_active = True
                        else:
                            if _qa_was_active:
                                slot_to_roll = {idx: r_face['roll_no'] for idx, r_face in enumerate(face_results) if r_face['roll_no'] > 0}
                                qa_checker.stop()
                                qa_checker.get_final_verdict(slot_to_roll)
                                _qa_was_active = False
                except: pass

            slot_to_roll = {idx: r_face['roll_no'] for idx, r_face in enumerate(face_results) if r_face['roll_no'] > 0}
            if qa_checker._active:
                is_correct = qa_checker.tick(slot_to_roll)
                if not is_correct:
                    for r_face in face_results:
                        r_face['wrong_student'] = True

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
                                "bbox": [int(x) for x in r["bbox"]],
                                "mar": float(r.get("mar", 0.0))
                            })
                        requests.post(f"{API_BASE}/telemetry/vision", json=payload, timeout=0.5)
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
