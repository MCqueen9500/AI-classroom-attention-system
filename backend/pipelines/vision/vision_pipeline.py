"""
pipelines/vision/vision_pipeline.py
=====================================
Main Vision Pipeline Orchestrator.

For each frame from the VideoSourceManager:
  1. Detect all faces in the frame.
  2. For each face, extract MediaPipe Face Mesh landmarks.
  3. Compute H_i (head pose), G_i (EAR), P_i (posture).
  4. Compute A_i(t) = 0.30*H + 0.50*G + 0.20*P.
  5. Persist the log entry to the database.
  6. Broadcast the result dict for WebSocket / dashboard consumption.

Runs in a background thread. Results are pushed to an async queue
that the FastAPI WebSocket handler reads from.
"""

import time
import logging
import threading
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any, Callable

import numpy as np

from hal.manager import VideoSourceManager
from pipelines.vision.face_detector import build_face_detector, FaceDetection
from pipelines.vision.landmark_extractor import LandmarkExtractor
from pipelines.vision.head_pose import HeadPoseScorer
from pipelines.vision.ear_scorer import EARScorer
from pipelines.vision.posture_scorer import PostureScorer
from db.crud import compute_instantaneous_attention
from core.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Per-student scorers (one EARScorer per student for consecutive frame state)
# ---------------------------------------------------------------------------
@dataclass
class StudentScorerSet:
    """Holds per-student scorer instances that maintain frame-level state."""
    ear:     EARScorer     = field(default_factory=EARScorer)
    posture: PostureScorer = field(default_factory=PostureScorer)


@dataclass
class FaceFrameResult:
    """Complete per-face scoring result for one frame."""
    bbox:         tuple
    h_i:          float
    g_i:          float
    p_i:          float
    a_i:          float
    ear:          float
    is_drowsy:    bool
    yaw:          float
    pitch:        float
    roll:         float
    confidence:   float
    landmarks_px: Optional[np.ndarray] = None
    roll_no:      Optional[int] = None
    timestamp:    float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Vision Pipeline
# ---------------------------------------------------------------------------
class VisionPipeline:
    """
    Processes webcam frames and emits per-face attention scores.

    Args:
        video_manager   : VideoSourceManager providing frames.
        session_id      : Active session UUID (from DB).
        on_frame_result : Optional callback(List[FaceFrameResult], annotated_frame)
                          called after each frame is processed.
                          Use this to push results to a WebSocket queue.
        db_session_factory : Optional async session factory for DB logging.
                             If None, results are emitted via callback only.
    """

    def __init__(
        self,
        video_manager: VideoSourceManager,
        session_id: str = "debug-session",
        on_frame_result: Optional[Callable] = None,
        db_session_factory=None,
    ):
        self._video = video_manager
        self._session_id = session_id
        self._on_frame_result = on_frame_result
        self._db_factory = db_session_factory

        # AI components
        self._detector   = build_face_detector(
            prefer="mediapipe",
            min_detection_confidence=settings.yolo_confidence,
        )
        self._extractor  = LandmarkExtractor(
            min_detection_confidence=settings.mediapipe_min_detection_confidence,
            min_tracking_confidence=settings.mediapipe_min_tracking_confidence,
        )
        self._hp_scorer  = HeadPoseScorer()

        # Per-student scorers (keyed by track_id or position index)
        self._student_scorers: Dict[int, StudentScorerSet] = {}

        # Session state
        self._running       = False
        self._paused        = False
        self._thread: Optional[threading.Thread] = None

        # Latest results (for polling)
        self._latest_results: List[FaceFrameResult] = []
        self._latest_frame:   Optional[np.ndarray]  = None
        self._lock = threading.Lock()

        # Collective inattention tracker (Edge Case 2)
        self._distraction_start: Optional[float] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def start(self):
        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True, name="VisionPipeline"
        )
        self._thread.start()
        logger.info("VisionPipeline: Started (session=%s)", self._session_id)

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
        self._detector.close()
        self._extractor.close()
        logger.info("VisionPipeline: Stopped.")

    def pause(self):
        self._paused = True
        logger.info("VisionPipeline: Paused.")

    def resume(self):
        self._paused = False
        self._distraction_start = None
        logger.info("VisionPipeline: Resumed.")

    @property
    def is_paused(self) -> bool:
        return self._paused

    # ------------------------------------------------------------------
    # Results access
    # ------------------------------------------------------------------
    def get_latest_results(self) -> List[FaceFrameResult]:
        with self._lock:
            return list(self._latest_results)

    def get_latest_frame(self) -> Optional[np.ndarray]:
        with self._lock:
            return self._latest_frame.copy() if self._latest_frame is not None else None

    def get_class_attention_pct(self) -> float:
        results = self.get_latest_results()
        if not results:
            return 0.0
        return round(sum(r.a_i for r in results) / len(results) * 100.0, 1)

    # ------------------------------------------------------------------
    # Internal processing loop
    # ------------------------------------------------------------------
    def _run_loop(self):
        import cv2
        while self._running:
            frame_data = self._video.get_frame(timeout=0.1)
            if frame_data is None:
                continue

            bgr = frame_data.image
            h, w = bgr.shape[:2]

            if self._paused:
                with self._lock:
                    self._latest_frame = bgr
                continue

            # -- Step 1: Detect faces
            detections: List[FaceDetection] = self._detector.detect(bgr)

            # -- Step 2-4: Per-face scoring
            frame_results: List[FaceFrameResult] = []
            for idx, det in enumerate(detections):
                result = self._process_face(det, bgr, w, h, idx)
                frame_results.append(result)

            # -- Step 5: Collective inattention check (Edge Case 2)
            self._check_collective_inattention(frame_results, len(detections))

            # -- Step 6: Update shared state
            with self._lock:
                self._latest_results = frame_results
                self._latest_frame   = bgr

            # -- Step 7: Fire callback (for WebSocket/DB logging)
            if self._on_frame_result:
                try:
                    self._on_frame_result(frame_results, bgr)
                except Exception as e:
                    logger.warning("VisionPipeline: on_frame_result callback error: %s", e)

    def _process_face(
        self,
        det: FaceDetection,
        full_frame: np.ndarray,
        frame_w: int,
        frame_h: int,
        face_idx: int,
    ) -> FaceFrameResult:
        """Process a single detected face through the full scoring pipeline."""
        x, y, bw, bh = det.bbox

        # Ensure per-student scorer state exists
        if face_idx not in self._student_scorers:
            self._student_scorers[face_idx] = StudentScorerSet()
        scorers = self._student_scorers[face_idx]

        # Step 2: Extract landmarks on the face crop
        landmarks = self._extractor.extract(det.face_crop, crop_x=x, crop_y=y)

        if landmarks is None:
            # No landmarks found: return neutral scores with low confidence
            return FaceFrameResult(
                bbox=det.bbox, h_i=0.5, g_i=0.5, p_i=0.5,
                a_i=compute_instantaneous_attention(0.5, 0.5, 0.5),
                ear=0.0, is_drowsy=False,
                yaw=0.0, pitch=0.0, roll=0.0,
                confidence=0.1,
            )

        # Step 3a: Head Pose → H_i
        yaw, pitch, roll, h_i = self._hp_scorer.compute(landmarks, frame_w, frame_h)

        # Step 3b: EAR → G_i
        ear, g_i, is_drowsy = scorers.ear.compute(landmarks)

        # Step 3c: Posture → P_i
        p_i = scorers.posture.compute(landmarks, frame_h, roll_deg=roll)

        # Step 4: Formula 1 → A_i(t)
        a_i = compute_instantaneous_attention(h_i, g_i, p_i)

        # Overall confidence = mean of detection confidence + landmark confidence
        confidence = round((det.confidence + landmarks.confidence) / 2.0, 3)

        return FaceFrameResult(
            bbox=det.bbox,
            h_i=round(h_i, 4),
            g_i=round(g_i, 4),
            p_i=round(p_i, 4),
            a_i=round(a_i, 4),
            ear=round(ear, 4),
            is_drowsy=is_drowsy,
            yaw=round(yaw, 2),
            pitch=round(pitch, 2),
            roll=round(roll, 2),
            confidence=confidence,
            landmarks_px=landmarks.landmarks_px,
        )

    def _check_collective_inattention(
        self,
        results: List[FaceFrameResult],
        total_faces: int,
    ):
        """
        Edge Case 2: If ≥85% of class distracted for ≥90s continuously,
        auto-pause and log intermission.
        """
        if total_faces == 0 or not results:
            self._distraction_start = None
            return

        distracted_count = sum(
            1 for r in results
            if r.a_i < (1.0 - settings.collective_distraction_threshold)
        )
        distraction_ratio = distracted_count / total_faces

        if distraction_ratio >= settings.collective_distraction_threshold:
            if self._distraction_start is None:
                self._distraction_start = time.time()
                logger.warning(
                    "VisionPipeline: Collective distraction started (%.0f%% distracted)",
                    distraction_ratio * 100,
                )
            elif (time.time() - self._distraction_start) >= settings.collective_distraction_duration_s:
                logger.warning(
                    "VisionPipeline: Collective distraction threshold reached! Auto-pausing..."
                )
                self.pause()
                self._distraction_start = None
        else:
            self._distraction_start = None
