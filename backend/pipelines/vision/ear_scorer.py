"""
pipelines/vision/ear_scorer.py
================================
Eye Aspect Ratio (EAR) based drowsiness and attention scorer → G_i

EAR Formula (Soukupova & Cech, 2016):
    EAR = (||p2-p6|| + ||p3-p5||) / (2 * ||p1-p4||)

Where for each eye:
    p1 = inner corner, p4 = outer corner  (horizontal axis)
    p2, p3 = upper eyelid points
    p5, p6 = lower eyelid points

  EAR ≈ 0.3+ → eyes wide open     → G_i = 1.0
  EAR ≈ 0.21 → drowsy/half-closed → G_i degrades
  EAR ≈ 0.0  → fully closed       → G_i = 0.0

Consecutive frame counter:
  If EAR < threshold for ≥ N consecutive frames → flag as drowsy.
  This prevents false flags from a single blink.
"""

import logging
import numpy as np
from .landmark_extractor import FaceLandmarks, LEFT_EYE_INDICES, RIGHT_EYE_INDICES  # noqa
from core.config import settings

logger = logging.getLogger(__name__)


def _euclidean(p1: np.ndarray, p2: np.ndarray) -> float:
    """Euclidean distance between two 2D points."""
    return float(np.linalg.norm(p1 - p2))


def compute_ear(eye_indices: list, landmarks_px: np.ndarray) -> float:
    """
    Compute EAR for one eye given 6 landmark pixel coordinates.

    Args:
        eye_indices  : list of 6 MediaPipe landmark indices [P1,P2,P3,P4,P5,P6]
        landmarks_px : (468, 2) pixel coordinates in full frame
    Returns:
        ear: float in [0, ~0.5]
    """
    p = [landmarks_px[i].astype(float) for i in eye_indices]
    # Vertical distances
    v1 = _euclidean(p[1], p[5])   # P2-P6
    v2 = _euclidean(p[2], p[4])   # P3-P5
    # Horizontal distance
    h  = _euclidean(p[0], p[3])   # P1-P4
    if h < 1e-6:
        return 0.0
    return (v1 + v2) / (2.0 * h)


class EARScorer:
    """
    Computes G_i eye-attention score using EAR with consecutive-frame drowsiness tracking.
    """

    def __init__(
        self,
        drowsy_threshold: float = None,
        closed_frames_threshold: int = None,
    ):
        self._ear_threshold  = drowsy_threshold     or settings.ear_drowsy_threshold
        self._frame_limit    = closed_frames_threshold or settings.ear_closed_frames_threshold
        self._consec_counter = 0   # consecutive frames below threshold
        self._is_drowsy      = False

    def compute(self, landmarks: FaceLandmarks) -> tuple:
        """
        Compute EAR and return G_i score with drowsiness flag.

        Returns:
            (ear: float, g_i: float, is_drowsy: bool)
        """
        px = landmarks.landmarks_px

        ear_left  = compute_ear(LEFT_EYE_INDICES,  px)
        ear_right = compute_ear(RIGHT_EYE_INDICES, px)
        ear_avg   = (ear_left + ear_right) / 2.0

        # Consecutive frame tracking
        if ear_avg < self._ear_threshold:
            self._consec_counter += 1
        else:
            self._consec_counter = 0

        self._is_drowsy = self._consec_counter >= self._frame_limit

        # Convert EAR to G_i [0,1]
        g_i = self._ear_to_score(ear_avg)
        return ear_avg, g_i, self._is_drowsy

    def _ear_to_score(self, ear: float) -> float:
        """
        Smooth mapping from EAR value → G_i score.

          EAR ≥ 0.30 : G_i = 1.0  (eyes wide open)
          EAR = 0.21 : G_i = 0.5  (threshold boundary)
          EAR = 0.0  : G_i = 0.0  (fully closed)
        """
        open_threshold = 0.30
        if ear >= open_threshold:
            return 1.0
        if ear <= 0.0:
            return 0.0
        # Linear interpolation between 0 and open_threshold
        return float(np.clip(ear / open_threshold, 0.0, 1.0))

    def reset(self):
        """Reset the consecutive frame counter (call at session start)."""
        self._consec_counter = 0
        self._is_drowsy = False
