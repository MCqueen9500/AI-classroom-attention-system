"""
pipelines/vision/landmark_extractor.py
========================================
Extracts 478 3D facial landmarks using MediaPipe Tasks FaceLandmarker API.
Compatible with mediapipe 0.10.x and 1.0.x (new Tasks API — solutions removed in 1.x).

Key landmark indices (same numbering as MediaPipe Face Mesh):
  HEAD_POSE_INDICES  → head_pose.py
  LEFT/RIGHT_EYE_INDICES → ear_scorer.py
  NOSE_TIP_INDEX     → posture_scorer.py
"""

import os
import logging
import numpy as np
from dataclasses import dataclass
from typing import Optional
import cv2

logger = logging.getLogger(__name__)

_MODELS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "models")
)

# ---------------------------------------------------------------------------
# Landmark Index Constants (same as classic Face Mesh 468-pt model)
# ---------------------------------------------------------------------------
HP_NOSE_TIP        = 1
HP_CHIN            = 152
HP_LEFT_EYE_LEFT   = 263
HP_RIGHT_EYE_RIGHT = 33
HP_LEFT_MOUTH      = 287
HP_RIGHT_MOUTH     = 57

HEAD_POSE_INDICES  = [HP_NOSE_TIP, HP_CHIN, HP_LEFT_EYE_LEFT,
                      HP_RIGHT_EYE_RIGHT, HP_LEFT_MOUTH, HP_RIGHT_MOUTH]

LEFT_EYE_INDICES   = [33, 160, 158, 133, 153, 144]
RIGHT_EYE_INDICES  = [362, 385, 387, 263, 373, 380]
NOSE_TIP_INDEX     = 1


@dataclass
class FaceLandmarks:
    """Extracted landmarks for a single face."""
    landmarks_norm: np.ndarray   # (N, 3) normalized [0,1]
    landmarks_px:   np.ndarray   # (N, 2) pixels in full frame
    confidence: float = 1.0
    crop_w: int = 0
    crop_h: int = 0
    crop_x: int = 0
    crop_y: int = 0


class LandmarkExtractor:
    """
    Extracts face landmarks using the MediaPipe Tasks FaceLandmarker.
    Falls back to a geometric approximation when model is unavailable.
    """

    def __init__(
        self,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
    ):
        self._use_mediapipe = False
        self._landmarker    = None
        self._mp            = None
        self._setup(min_detection_confidence, min_tracking_confidence)

    def _setup(self, det_conf: float, track_conf: float):
        model_path = os.path.join(_MODELS_DIR, "face_landmarker.task")
        if not os.path.exists(model_path):
            logger.warning(
                "LandmarkExtractor: face_landmarker.task not found. "
                "Run: python scripts/download_models.py  — using geometric fallback."
            )
            return
        try:
            import mediapipe as mp
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision as mp_vision

            base_options = mp_python.BaseOptions(model_asset_path=model_path)
            options = mp_vision.FaceLandmarkerOptions(
                base_options=base_options,
                num_faces=1,
                min_face_detection_confidence=det_conf,
                min_face_presence_confidence=det_conf,
                min_tracking_confidence=track_conf,
                output_face_blendshapes=False,
                output_facial_transformation_matrixes=False,
            )
            self._landmarker    = mp_vision.FaceLandmarker.create_from_options(options)
            self._mp            = mp
            self._use_mediapipe = True
            logger.info("LandmarkExtractor: Using MediaPipe Tasks FaceLandmarker")
        except Exception as e:
            logger.warning("LandmarkExtractor: Tasks API failed (%s) — geometric fallback active", e)

    def extract(
        self,
        bgr_frame: np.ndarray,
        crop_x: int = 0,
        crop_y: int = 0,
    ) -> Optional[FaceLandmarks]:
        if self._use_mediapipe:
            return self._extract_tasks(bgr_frame, crop_x, crop_y)
        return self._extract_geometric(bgr_frame, crop_x, crop_y)

    def _extract_tasks(
        self,
        bgr_frame: np.ndarray,
        crop_x: int,
        crop_y: int,
    ) -> Optional[FaceLandmarks]:
        h, w = bgr_frame.shape[:2]
        if h < 20 or w < 20:
            return None
        rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
        mp_image = self._mp.Image(
            image_format=self._mp.ImageFormat.SRGB,
            data=rgb,
        )
        result = self._landmarker.detect(mp_image)
        if not result.face_landmarks:
            return None

        face = result.face_landmarks[0]
        # Tasks API: each landmark has .x, .y, .z in normalized [0,1]
        norm = np.array([[lm.x, lm.y, lm.z] for lm in face], dtype=np.float32)
        n = len(norm)

        px = np.column_stack([
            np.clip((norm[:, 0] * w + crop_x).astype(int), 0, 99999),
            np.clip((norm[:, 1] * h + crop_y).astype(int), 0, 99999),
        ])

        return FaceLandmarks(
            landmarks_norm=norm,
            landmarks_px=px,
            confidence=1.0,
            crop_w=w, crop_h=h,
            crop_x=crop_x, crop_y=crop_y,
        )

    def _extract_geometric(
        self,
        bgr_frame: np.ndarray,
        crop_x: int,
        crop_y: int,
    ) -> Optional[FaceLandmarks]:
        """Synthetic landmark positions based on face bounding box geometry."""
        h, w = bgr_frame.shape[:2]
        if h < 20 or w < 20:
            return None

        norm = np.zeros((478, 3), dtype=np.float32)  # 478 pts in landmarker

        # Key points approximated from face proportions
        norm[NOSE_TIP_INDEX]      = [0.50, 0.55, 0.0]
        norm[HP_CHIN]             = [0.50, 0.85, 0.0]
        norm[HP_LEFT_EYE_LEFT]    = [0.66, 0.40, 0.0]
        norm[HP_RIGHT_EYE_RIGHT]  = [0.34, 0.40, 0.0]
        norm[HP_LEFT_MOUTH]       = [0.62, 0.72, 0.0]
        norm[HP_RIGHT_MOUTH]      = [0.38, 0.72, 0.0]

        # Left eye (open)
        eye_l = {33:[0.34,0.40,0], 160:[0.31,0.37,0], 158:[0.27,0.37,0],
                 133:[0.22,0.40,0], 153:[0.27,0.43,0], 144:[0.31,0.43,0]}
        # Right eye (open)
        eye_r = {362:[0.66,0.40,0], 385:[0.69,0.37,0], 387:[0.73,0.37,0],
                 263:[0.78,0.40,0], 373:[0.73,0.43,0], 380:[0.69,0.43,0]}
        for idx, pos in {**eye_l, **eye_r}.items():
            if idx < 478:
                norm[idx] = pos

        px = np.column_stack([
            (norm[:, 0] * w + crop_x).astype(int),
            (norm[:, 1] * h + crop_y).astype(int),
        ])

        return FaceLandmarks(
            landmarks_norm=norm, landmarks_px=px,
            confidence=0.4,
            crop_w=w, crop_h=h,
            crop_x=crop_x, crop_y=crop_y,
        )

    def close(self):
        if self._landmarker:
            self._landmarker.close()
