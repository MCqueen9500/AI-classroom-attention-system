"""
scripts/run_vision_debug.py
============================
Live real-time debug viewer for the Vision Pipeline.
Opens your webcam, runs the full A_i(t) scoring pipeline, and displays:
  - Bounding box per face (color-coded by attention score)
  - Head pose axes (Yaw/Pitch/Roll arrows)
  - Score breakdown bar (H_i | G_i | P_i | A_i)
  - Drowsiness flag
  - HUD with class-level attention %

Controls:
  Q  → quit
  P  → pause/resume monitoring
  S  → print current scores to terminal

Usage:
    python scripts/run_vision_debug.py
    python scripts/run_vision_debug.py --source mock   (no webcam)
"""

import sys
import os
import time
import argparse
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

import cv2
import numpy as np

from hal.video_source import WebcamVideoSource, MockVideoSource
from hal.manager import VideoSourceManager
from pipelines.vision.face_detector import build_face_detector
from pipelines.vision.landmark_extractor import LandmarkExtractor
from pipelines.vision.head_pose import HeadPoseScorer
from pipelines.vision.ear_scorer import EARScorer
from pipelines.vision.posture_scorer import PostureScorer
from pipelines.vision.overlay import draw_frame_overlay
from db.crud import compute_instantaneous_attention
from core.config import settings
from core.logging_config import setup_logging

setup_logging()
logger = logging.getLogger("vision_debug")


def run_debug(use_mock: bool = False):
    # ── Setup HAL ────────────────────────────────────────────────
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
        logger.error("Failed to open video source. Exiting.")
        sys.exit(1)

    # ── Setup AI components ───────────────────────────────────────
    detector  = build_face_detector(prefer="mediapipe", min_detection_confidence=0.5)
    extractor = LandmarkExtractor()
    hp_scorer = HeadPoseScorer()
    ear_scorers  = {}   # face_idx -> EARScorer
    post_scorers = {}   # face_idx -> PostureScorer

    logger.info("Vision Debug Viewer started. Press Q to quit, P to pause.")

    frame_count = 0
    paused = False
    fps_start = time.time()

    try:
        while True:
            frame_data = video_mgr.get_frame(timeout=0.2)
            if frame_data is None:
                continue

            bgr = frame_data.image
            fh, fw = bgr.shape[:2]
            frame_count += 1

            if paused:
                display = bgr.copy()
                cv2.putText(display, "PAUSED - Press P to resume",
                            (fw // 2 - 160, fh // 2),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 60, 255), 2)
                cv2.imshow("Classroom Vision Debug", display)
                key = cv2.waitKey(30) & 0xFF
                if key == ord("q"):
                    break
                if key == ord("p"):
                    paused = False
                continue

            # ── Face Detection ────────────────────────────────────────
            detections = detector.detect(bgr)
            face_results = []

            for idx, det in enumerate(detections):
                x, y, bw, bh = det.bbox

                if idx not in ear_scorers:
                    ear_scorers[idx]  = EARScorer()
                    post_scorers[idx] = PostureScorer()

                # Landmark extraction on face crop
                landmarks = extractor.extract(det.face_crop, crop_x=x, crop_y=y)
                if landmarks is None:
                    face_results.append({"bbox": det.bbox, "h_i": 0.5, "g_i": 0.5,
                                         "p_i": 0.5, "a_i": 0.5, "ear": 0.0,
                                         "is_drowsy": False, "yaw": 0.0,
                                         "pitch": 0.0, "roll": 0.0, "landmarks_px": None})
                    continue

                yaw, pitch, roll, h_i = hp_scorer.compute(landmarks, fw, fh)
                ear, g_i, is_drowsy   = ear_scorers[idx].compute(landmarks)
                p_i                   = post_scorers[idx].compute(landmarks, fh, roll)
                a_i                   = compute_instantaneous_attention(h_i, g_i, p_i)

                face_results.append({
                    "bbox": det.bbox,
                    "h_i": h_i, "g_i": g_i, "p_i": p_i, "a_i": a_i,
                    "ear": ear, "is_drowsy": is_drowsy,
                    "yaw": yaw, "pitch": pitch, "roll": roll,
                    "landmarks_px": landmarks.landmarks_px,
                })

            # ── Class-level attention ─────────────────────────────────
            class_pct = (
                sum(r["a_i"] for r in face_results) / len(face_results) * 100.0
                if face_results else 0.0
            )

            # ── Overlay ───────────────────────────────────────────────
            annotated = draw_frame_overlay(bgr, face_results, class_pct, paused)

            # FPS display
            elapsed = time.time() - fps_start
            if elapsed > 0:
                fps = frame_count / elapsed
                cv2.putText(annotated, f"FPS: {fps:.1f}",
                            (fw - 80, 20), cv2.FONT_HERSHEY_SIMPLEX,
                            0.5, (200, 200, 200), 1, cv2.LINE_AA)

            cv2.imshow("Classroom Vision Debug", annotated)

            # ── Key controls ──────────────────────────────────────────
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            elif key == ord("p"):
                paused = not paused
                logger.info("Pipeline %s", "PAUSED" if paused else "RESUMED")
            elif key == ord("s"):
                print(f"\n{'='*50}")
                print(f"Frame {frame_count} | Faces: {len(face_results)} | Class: {class_pct:.1f}%")
                for i, r in enumerate(face_results):
                    print(f"  Face {i}: H={r['h_i']:.2f} G={r['g_i']:.2f} "
                          f"P={r['p_i']:.2f} A={r['a_i']:.2f} "
                          f"EAR={r['ear']:.3f} "
                          f"Y={r['yaw']:.1f} P={r['pitch']:.1f} R={r['roll']:.1f}")
                print(f"{'='*50}\n")

    finally:
        video_mgr.stop()
        detector.close()
        extractor.close()
        cv2.destroyAllWindows()
        logger.info("Vision Debug Viewer closed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Vision Pipeline Debug Viewer")
    parser.add_argument("--source", choices=["webcam", "mock"], default="webcam")
    args = parser.parse_args()
    run_debug(use_mock=(args.source == "mock"))
