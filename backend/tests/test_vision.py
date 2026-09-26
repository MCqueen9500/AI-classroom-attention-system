"""
backend/tests/test_vision.py
==============================
Unit tests for Vision Pipeline components.
All tests use synthetic data — no webcam or AI model required.
"""

import sys
import numpy as np
import pytest
import time

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

from pipelines.vision.ear_scorer import compute_ear, EARScorer, LEFT_EYE_INDICES, RIGHT_EYE_INDICES
from pipelines.vision.posture_scorer import PostureScorer
from pipelines.vision.head_pose import HeadPoseScorer
from pipelines.vision.landmark_extractor import FaceLandmarks
from pipelines.vision.face_detector import YuNetFaceDetector, FaceDetection
from pipelines.vision.overlay import draw_frame_overlay, draw_score_bar, draw_hud
from db.crud import compute_instantaneous_attention


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_landmarks(override: dict = None) -> FaceLandmarks:
    """Create synthetic FaceLandmarks with default eye-open positions."""
    norm = np.zeros((468, 3), dtype=np.float32)

    # Default: open left eye (EAR ≈ 0.35 → healthy)
    # LEFT_EYE_INDICES = [33, 160, 158, 133, 153, 144]
    # P1(inner), P2(upper-inner), P3(upper-outer), P4(outer), P5(lower-outer), P6(lower-inner)
    eye_pts = {
        33:  [0.34, 0.40, 0], 160: [0.31, 0.37, 0],
        158: [0.27, 0.37, 0], 133: [0.22, 0.40, 0],
        153: [0.27, 0.43, 0], 144: [0.31, 0.43, 0],
        362: [0.66, 0.40, 0], 385: [0.69, 0.37, 0],
        387: [0.73, 0.37, 0], 263: [0.78, 0.40, 0],
        373: [0.73, 0.43, 0], 380: [0.69, 0.43, 0],
    }
    for idx, pos in eye_pts.items():
        norm[idx] = pos

    # Nose tip & head pose points
    norm[1]   = [0.50, 0.55, 0.0]
    norm[152] = [0.50, 0.85, 0.0]
    norm[33]  = [0.34, 0.40, 0.0]
    norm[263] = [0.66, 0.40, 0.0]
    norm[57]  = [0.38, 0.72, 0.0]
    norm[287] = [0.62, 0.72, 0.0]

    if override:
        for idx, val in override.items():
            norm[idx] = val

    px = np.column_stack([
        (norm[:, 0] * 640).astype(int),
        (norm[:, 1] * 480).astype(int),
    ])

    return FaceLandmarks(
        landmarks_norm=norm,
        landmarks_px=px,
        confidence=0.95,
        crop_w=640,
        crop_h=480,
        crop_x=0,
        crop_y=0,
    )


# ---------------------------------------------------------------------------
# Formula 1
# ---------------------------------------------------------------------------

class TestInstantaneousAttention:
    def test_perfect_score(self):
        a = compute_instantaneous_attention(1.0, 1.0, 1.0)
        assert a == 1.0

    def test_zero_score(self):
        a = compute_instantaneous_attention(0.0, 0.0, 0.0)
        assert a == 0.0

    def test_weights_applied(self):
        # Only G_i=1.0, rest 0 → A = 0.50
        a = compute_instantaneous_attention(0.0, 1.0, 0.0)
        assert abs(a - 0.50) < 1e-4

    def test_clamped_to_one(self):
        a = compute_instantaneous_attention(1.5, 1.5, 1.5)
        assert a == 1.0


# ---------------------------------------------------------------------------
# EAR Scorer
# ---------------------------------------------------------------------------

class TestEARScorer:
    def test_open_eyes_high_score(self):
        lm = make_landmarks()
        scorer = EARScorer()
        ear, g_i, drowsy = scorer.compute(lm)
        assert ear > 0.15, "EAR should be above minimal open-eye threshold"
        assert g_i > 0.5,  "G_i should be above 0.5 for open eyes"
        assert drowsy is False

    def test_closed_eyes_low_score(self):
        # Make eyelids overlap (P2,P3 same height as P5,P6 → EAR ≈ 0)
        closed_pts = {
            160: [0.31, 0.40, 0], 158: [0.27, 0.40, 0],   # Upper eyelid at same Y as lower
            153: [0.27, 0.40, 0], 144: [0.31, 0.40, 0],
            385: [0.69, 0.40, 0], 387: [0.73, 0.40, 0],
            373: [0.73, 0.40, 0], 380: [0.69, 0.40, 0],
        }
        lm = make_landmarks(override=closed_pts)
        scorer = EARScorer()
        ear, g_i, _ = scorer.compute(lm)
        assert ear < 0.10, f"EAR {ear:.3f} should be near 0 for closed eyes"
        assert g_i < 0.35

    def test_consecutive_drowsiness_flag(self):
        closed_pts = {
            160: [0.31, 0.405, 0], 158: [0.27, 0.405, 0],
            153: [0.27, 0.395, 0], 144: [0.31, 0.395, 0],
            385: [0.69, 0.405, 0], 387: [0.73, 0.405, 0],
            373: [0.73, 0.395, 0], 380: [0.69, 0.395, 0],
        }
        lm = make_landmarks(override=closed_pts)
        scorer = EARScorer(drowsy_threshold=0.21, closed_frames_threshold=3)
        for _ in range(2):
            _, _, drowsy = scorer.compute(lm)
            assert not drowsy   # Not yet — below threshold count
        _, _, drowsy = scorer.compute(lm)
        assert drowsy           # 3rd frame → flagged

    def test_reset(self):
        closed_pts = {
            160: [0.31, 0.405, 0], 158: [0.27, 0.405, 0],
            153: [0.27, 0.395, 0], 144: [0.31, 0.395, 0],
            385: [0.69, 0.405, 0], 387: [0.73, 0.405, 0],
            373: [0.73, 0.395, 0], 380: [0.69, 0.395, 0],
        }
        lm = make_landmarks(override=closed_pts)
        scorer = EARScorer(closed_frames_threshold=3)
        for _ in range(3):
            scorer.compute(lm)
        scorer.reset()
        _, _, drowsy = scorer.compute(lm)
        assert not drowsy


# ---------------------------------------------------------------------------
# Posture Scorer
# ---------------------------------------------------------------------------

class TestPostureScorer:
    def test_face_in_normal_zone(self):
        lm = make_landmarks()  # Nose at (0.50, 0.55) → norm_y=0.55 in 480px frame
        scorer = PostureScorer()
        p_i = scorer.compute(lm, frame_h=480, roll_deg=0.0)
        assert p_i >= 0.75, f"Expected high posture score, got {p_i}"

    def test_face_very_low_slouching(self):
        # Nose tip near bottom of frame → slouching
        override = {1: [0.5, 0.95, 0]}  # norm_y=0.95
        lm = make_landmarks(override=override)
        lm.landmarks_px[1] = [320, int(0.95 * 480)]
        scorer = PostureScorer()
        p_i = scorer.compute(lm, frame_h=480, roll_deg=0.0)
        assert p_i < 0.5, f"Expected low posture for slouching, got {p_i}"

    def test_extreme_roll_penalty(self):
        lm = make_landmarks()
        scorer = PostureScorer()
        p_upright = scorer.compute(lm, frame_h=480, roll_deg=5.0)
        p_tilted  = scorer.compute(lm, frame_h=480, roll_deg=60.0)
        assert p_tilted < p_upright


# ---------------------------------------------------------------------------
# HaarCascade Detector (no model download needed)
# ---------------------------------------------------------------------------

class TestYuNetFaceDetector:
    def test_returns_list_on_blank_frame(self):
        import os
        model_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "models", "face_detection_yunet_2023mar.onnx")
        )
        if not os.path.exists(model_path):
            pytest.skip("YuNet model not downloaded yet — run: python scripts/download_models.py")
        blank = np.zeros((480, 640, 3), dtype=np.uint8)
        det = YuNetFaceDetector(model_path=model_path)
        results = det.detect(blank)
        # blank frame should return an empty list (no faces)
        assert isinstance(results, list)
        assert len(results) == 0


# ---------------------------------------------------------------------------
# Overlay (pure rendering tests — no display window)
# ---------------------------------------------------------------------------

class TestOverlay:
    def test_draw_frame_overlay_returns_same_shape(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = draw_frame_overlay(frame, [], class_attention_pct=75.0)
        assert result.shape == frame.shape

    def test_draw_with_face_results(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        face_results = [{
            "bbox": (50, 50, 100, 120),
            "h_i": 0.9, "g_i": 0.85, "p_i": 0.80, "a_i": 0.86,
            "ear": 0.32, "is_drowsy": False,
            "yaw": 5.0, "pitch": -3.0, "roll": 2.0,
            "landmarks_px": None,
        }]
        result = draw_frame_overlay(frame, face_results, class_attention_pct=86.0)
        assert result.shape == (480, 640, 3)
        # Frame should have been modified (pixel sum should differ from zeros)
        assert result.sum() > 0
