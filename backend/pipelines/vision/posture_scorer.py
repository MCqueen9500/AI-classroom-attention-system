"""
pipelines/vision/posture_scorer.py
=====================================
Estimates posture score P_i from face geometry in the frame.

Since the camera captures faces (not full body), we use two face-based proxies:
  1. Vertical position of nose tip in frame:
     - Face in upper 30-60% of frame = normal upright seating → P high
     - Face very low (slouching) or very high (leaning back) → P drops
  2. Roll angle contribution:
     - Significant head tilt (e.g., head on desk) → P drops

Score range: 0.0 (clearly slouching/absent) to 1.0 (upright, correct posture)
"""

import logging
import numpy as np
from .landmark_extractor import FaceLandmarks, NOSE_TIP_INDEX

logger = logging.getLogger(__name__)


class PostureScorer:
    """
    Computes posture score P_i from face vertical position and tilt.
    """

    def __init__(
        self,
        expected_face_zone_top: float = 0.15,    # Face ideally between 15% and 75% of frame height
        expected_face_zone_bottom: float = 0.75,
        roll_penalty_threshold: float = 25.0,    # degrees of tilt before penalizing
    ):
        self._zone_top    = expected_face_zone_top
        self._zone_bot    = expected_face_zone_bottom
        self._roll_thr    = roll_penalty_threshold

    def compute(
        self,
        landmarks: FaceLandmarks,
        frame_h: int,
        roll_deg: float = 0.0,
    ) -> float:
        """
        Compute P_i posture score.

        Args:
            landmarks : FaceLandmarks with nose tip position
            frame_h   : Full frame height in pixels
            roll_deg  : Head roll angle in degrees (from head_pose.py)
        Returns:
            p_i : float [0.0, 1.0]
        """
        if frame_h <= 0:
            return 0.5

        # 1. Nose tip Y in full frame
        nose_px_y = landmarks.landmarks_px[NOSE_TIP_INDEX][1]
        nose_norm_y = nose_px_y / frame_h   # [0,1] where 0=top, 1=bottom

        # 2. Position score: smooth decay outside expected zone
        pos_score = self._position_score(nose_norm_y)

        # 3. Roll penalty: heavy tilt suggests fatigue or head-on-desk
        roll_score = self._roll_score(roll_deg)

        # 4. Combine: position matters more than roll for posture
        p_i = float(np.clip(0.75 * pos_score + 0.25 * roll_score, 0.0, 1.0))
        return round(p_i, 4)

    def _position_score(self, norm_y: float) -> float:
        """
        Score based on vertical face position in frame.
           norm_y in [zone_top, zone_bot]         → 1.0
           norm_y < zone_top (too high/leaning back) → decays
           norm_y > zone_bot (too low/slouching)   → decays
        """
        if self._zone_top <= norm_y <= self._zone_bot:
            return 1.0

        if norm_y < self._zone_top:
            # Above expected zone
            dist = self._zone_top - norm_y
            # Decay over 0.15 (15% of frame height)
            return float(np.clip(1.0 - (dist / 0.15), 0.0, 1.0))
        else:
            # Below expected zone (slouching)
            dist = norm_y - self._zone_bot
            return float(np.clip(1.0 - (dist / 0.20), 0.0, 1.0))

    def _roll_score(self, roll_deg: float) -> float:
        """Score based on head roll/tilt."""
        if abs(roll_deg) <= self._roll_thr:
            return 1.0
        excess = abs(roll_deg) - self._roll_thr
        # Decay to 0 over an additional 30 degrees
        return float(np.clip(1.0 - (excess / 30.0), 0.0, 1.0))
