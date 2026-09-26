"""
pipelines/vision/head_pose.py
==============================
Estimates 3D head pose (Yaw, Pitch, Roll) from 6 key facial landmarks
using OpenCV's solvePnP algorithm.

Returns H_i score (0.0 to 1.0):
  1.0 = facing board/camera directly
  0.0 = fully turned away / extreme tilt

Mathematical model:
  The 6 landmarks are matched to a canonical 3D face model.
  solvePnP produces a rotation vector (rvec), which is converted to
  Euler angles (Yaw/Pitch/Roll) via the rotation matrix.
  H_i = sigmoid-like decay applied to each angle against thresholds.
"""

import logging
import numpy as np
from typing import Optional, Tuple
import cv2

from .landmark_extractor import FaceLandmarks, HEAD_POSE_INDICES
from core.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Canonical 3D face model (unit: mm, centered at origin)
# Reference: Guo et al. (2020); common literature values
# ---------------------------------------------------------------------------
FACE_3D_MODEL = np.array([
    [0.0,    0.0,    0.0  ],   # Nose tip        (index 1)
    [0.0,   -63.6,  -12.5],   # Chin            (index 152)
    [-43.3,  32.7,  -26.0],   # Left eye outer  (index 263)
    [43.3,   32.7,  -26.0],   # Right eye outer (index 33)
    [-28.9, -28.9,  -24.1],   # Left mouth      (index 287)
    [28.9,  -28.9,  -24.1],   # Right mouth     (index 57)
], dtype=np.float64)


class HeadPoseScorer:
    """
    Estimates head orientation and converts it to an attention score H_i.
    """

    def __init__(
        self,
        yaw_threshold: float = None,
        pitch_threshold: float = None,
    ):
        self._yaw_thr   = yaw_threshold   or settings.head_yaw_threshold    # degrees
        self._pitch_thr = pitch_threshold or settings.head_pitch_threshold   # degrees

    def _get_camera_matrix(self, frame_w: int, frame_h: int) -> np.ndarray:
        """Approximate camera intrinsics assuming standard focal length."""
        focal_length = frame_w
        center = (frame_w / 2.0, frame_h / 2.0)
        return np.array([
            [focal_length, 0,            center[0]],
            [0,            focal_length, center[1]],
            [0,            0,            1        ],
        ], dtype=np.float64)

    def compute(
        self,
        landmarks: FaceLandmarks,
        frame_w: int,
        frame_h: int,
    ) -> Tuple[float, float, float, float]:
        """
        Compute Yaw, Pitch, Roll angles and attention score H_i.

        Returns:
            (yaw_deg, pitch_deg, roll_deg, H_i)
        """
        # Extract the 6 key landmark pixel positions in the full frame
        pts_2d = np.array(
            [landmarks.landmarks_px[idx] for idx in HEAD_POSE_INDICES],
            dtype=np.float64,
        )

        # Use the crop-level normalized coordinates to refine
        pts_norm = np.array(
            [landmarks.landmarks_norm[idx] for idx in HEAD_POSE_INDICES],
            dtype=np.float64,
        )

        # Pixel coordinates in full frame
        full_pts = np.column_stack([
            pts_norm[:, 0] * landmarks.crop_w + landmarks.crop_x,
            pts_norm[:, 1] * landmarks.crop_h + landmarks.crop_y,
        ])

        cam_matrix = self._get_camera_matrix(frame_w, frame_h)
        dist_coeffs = np.zeros((4, 1), dtype=np.float64)

        success, rvec, tvec = cv2.solvePnP(
            FACE_3D_MODEL,
            full_pts,
            cam_matrix,
            dist_coeffs,
            flags=cv2.SOLVEPNP_ITERATIVE,
        )

        if not success:
            return 0.0, 0.0, 0.0, 0.5   # uncertain neutral

        rmat, _ = cv2.Rodrigues(rvec)

        # Decompose rotation matrix to Euler angles
        sy = np.sqrt(rmat[0, 0] ** 2 + rmat[1, 0] ** 2)
        singular = sy < 1e-6

        if not singular:
            roll  = np.degrees(np.arctan2( rmat[2, 1],  rmat[2, 2]))
            pitch = np.degrees(np.arctan2(-rmat[2, 0],  sy))
            yaw   = np.degrees(np.arctan2( rmat[1, 0],  rmat[0, 0]))
        else:
            roll  = np.degrees(np.arctan2(-rmat[1, 2],  rmat[1, 1]))
            pitch = np.degrees(np.arctan2(-rmat[2, 0],  sy))
            yaw   = 0.0

        h_i = self._angles_to_score(yaw, pitch, roll)
        return float(yaw), float(pitch), float(roll), float(h_i)

    def _angles_to_score(self, yaw: float, pitch: float, roll: float) -> float:
        """
        Convert Euler angles to H_i score [0,1].

        Uses a smooth cosine decay so the score degrades gradually
        rather than dropping sharply at threshold edges.
        """
        def soft_score(angle_deg: float, threshold: float) -> float:
            """1.0 when |angle| < threshold/2, decays to 0 at threshold."""
            half = threshold / 2.0
            if abs(angle_deg) <= half:
                return 1.0
            if abs(angle_deg) >= threshold:
                return 0.0
            # Smooth cosine interpolation in the decay zone
            t = (abs(angle_deg) - half) / half
            return float(0.5 * (1.0 + np.cos(np.pi * t)))

        h_yaw   = soft_score(yaw,   self._yaw_thr)
        h_pitch = soft_score(pitch, self._pitch_thr)
        # Roll contributes less — mostly cosmetic tilt
        h_roll  = soft_score(roll, 45.0)

        # Weighted combination: yaw and pitch matter most
        return float(np.clip(0.50 * h_yaw + 0.40 * h_pitch + 0.10 * h_roll, 0.0, 1.0))
