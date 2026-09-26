"""
backend/tests/test_lip_activity.py
=====================================
Unit tests for Lip Activity Tracker and QA Speaker Checker.
No webcam, no models — pure numpy synthetic data.
"""

import sys, os
import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pipelines.vision.lip_activity import (
    LipActivityTracker,
    LipActivityResult,
    QASpeakerChecker,
    SpeakerCheckResult,
    UPPER_LIP_IDX,
    LOWER_LIP_IDX,
    NOSE_TIP_IDX,
    CHIN_IDX,
)


# ---------------------------------------------------------------------------
# Helpers — synthetic landmark arrays
# ---------------------------------------------------------------------------

def make_landmarks(n=478, lip_aperture_px=5.0, face_height_px=100.0) -> np.ndarray:
    """
    Create a synthetic 478-point landmark array (all zeros except key points).
    face_height = distance from nose tip (idx=1) to chin (idx=152).
    lip_aperture = distance from upper (idx=13) to lower (idx=14) lip.
    """
    pts = np.zeros((n, 2), dtype=np.float32)
    # Nose tip at (240, 200), chin at (240, 200 + face_height)
    pts[NOSE_TIP_IDX] = [240, 200]
    pts[CHIN_IDX]     = [240, 200 + face_height_px]
    # Upper lip center at (240, 240), lower lip at (240, 240 + aperture)
    pts[UPPER_LIP_IDX] = [240, 240]
    pts[LOWER_LIP_IDX] = [240, 240 + lip_aperture_px]
    return pts


def feed_frames(tracker, face_slot, apertures, face_height=100.0):
    """Feed multiple frames with varying aperture to simulate speech."""
    for ap in apertures:
        lm = make_landmarks(lip_aperture_px=ap, face_height_px=face_height)
        tracker.update(face_slot, lm, frame_h=480)


# ---------------------------------------------------------------------------
# LipActivityTracker Tests
# ---------------------------------------------------------------------------

class TestLipActivityTracker:

    def test_update_returns_lar(self):
        tracker = LipActivityTracker()
        lm = make_landmarks(lip_aperture_px=10.0, face_height_px=100.0)
        lar = tracker.update(0, lm, frame_h=480)
        assert 0.0 < lar < 1.0

    def test_silent_face_low_variance(self):
        tracker = LipActivityTracker(window_frames=15, min_frames=5)
        # Silent = constant small aperture
        silent = [2.0] * 15
        feed_frames(tracker, face_slot=0, apertures=silent)
        scores = tracker.get_activity_scores()
        assert scores[0] < 0.001   # very low variance

    def test_speaking_face_high_variance(self):
        tracker = LipActivityTracker(window_frames=15, min_frames=5)
        # Speaking = oscillating aperture (open/close pattern)
        speaking = [2, 18, 3, 17, 2, 19, 3, 16, 2, 18, 3, 17, 2, 19, 3]
        feed_frames(tracker, face_slot=1, apertures=speaking)
        scores = tracker.get_activity_scores()
        assert scores[1] > 0.001   # high variance

    def test_get_speaker_returns_highest_variance_slot(self):
        tracker = LipActivityTracker(
            window_frames=15, min_frames=5, speaking_threshold=0.0001
        )
        # Face 0: silent
        feed_frames(tracker, 0, [2.0] * 15)
        # Face 1: speaking (high variance)
        feed_frames(tracker, 1, [2, 20, 3, 18, 2, 20, 2, 19, 3, 18, 2, 20, 3, 17, 2])
        # Face 2: also silent
        feed_frames(tracker, 2, [1.5] * 15)

        speaker = tracker.get_speaker()
        assert speaker == 1   # Face 1 should be identified as speaker

    def test_no_speech_returns_none(self):
        tracker = LipActivityTracker(
            window_frames=15, min_frames=5, speaking_threshold=0.01
        )
        # All faces silent — variance below threshold
        feed_frames(tracker, 0, [2.0] * 15)
        feed_frames(tracker, 1, [2.1] * 15)
        assert tracker.get_speaker() is None

    def test_insufficient_frames_returns_zero_score(self):
        tracker = LipActivityTracker(min_frames=10)
        # Only 3 frames fed — below min_frames
        feed_frames(tracker, 0, [2, 18, 2])
        scores = tracker.get_activity_scores()
        assert scores[0] == 0.0

    def test_reset_slot_clears_history(self):
        tracker = LipActivityTracker(window_frames=15, min_frames=5)
        feed_frames(tracker, 0, [2, 18, 3, 17, 2] * 3)
        tracker.reset_slot(0)
        scores = tracker.get_activity_scores()
        assert 0 not in scores

    def test_reset_all_clears_everything(self):
        tracker = LipActivityTracker(window_frames=15, min_frames=5)
        feed_frames(tracker, 0, [2, 18, 3] * 5)
        feed_frames(tracker, 1, [1.5] * 15)
        tracker.reset_all()
        assert tracker.get_activity_scores() == {}

    def test_get_all_results_structure(self):
        tracker = LipActivityTracker(
            window_frames=15, min_frames=5, speaking_threshold=0.0001
        )
        feed_frames(tracker, 0, [2, 18, 2, 17, 2, 19, 2, 18, 2, 17, 2, 19, 2, 18, 2])
        results = tracker.get_all_results()
        assert len(results) == 1
        r = results[0]
        assert hasattr(r, "face_slot")
        assert hasattr(r, "lip_aperture")
        assert hasattr(r, "activity_score")
        assert hasattr(r, "is_speaking")

    def test_normalization_by_face_height(self):
        """Same aperture but different face height → different LAR."""
        tracker = LipActivityTracker()
        lm_close  = make_landmarks(lip_aperture_px=10.0, face_height_px=50.0)
        lm_far    = make_landmarks(lip_aperture_px=10.0, face_height_px=150.0)
        lar_close = tracker.update(0, lm_close, frame_h=480)
        lar_far   = tracker.update(1, lm_far,   frame_h=480)
        assert lar_close > lar_far   # same px aperture, smaller face → larger ratio


# ---------------------------------------------------------------------------
# QASpeakerChecker Tests
# ---------------------------------------------------------------------------

class TestQASpeakerChecker:

    def _make_checker(self, threshold=0.0001):
        tracker = LipActivityTracker(
            window_frames=15, min_frames=5, speaking_threshold=threshold
        )
        checker = QASpeakerChecker(lip_tracker=tracker)
        return tracker, checker

    def test_correct_student_answers(self):
        """Roll 14 is asked, Roll 14 (slot 0) is speaking → is_correct=True."""
        tracker, checker = self._make_checker()

        # Slot 0 = Roll 14 (asked and speaking)
        # Slot 1 = Roll 7  (silent)
        slot_to_roll = {0: 14, 1: 7}
        checker.start(asked_roll=14)

        # Feed 20 frames: slot 0 speaking, slot 1 silent
        speaking = [2, 18, 3, 17, 2, 19, 2, 18, 3, 17, 2, 19, 2, 18, 3, 17, 2, 19, 2, 18]
        silent   = [2.0] * 20

        for i, (sp, si) in enumerate(zip(speaking, silent)):
            lm_speak = make_landmarks(lip_aperture_px=sp)
            lm_silent = make_landmarks(lip_aperture_px=si)
            tracker.update(0, lm_speak,  frame_h=480)
            tracker.update(1, lm_silent, frame_h=480)
            checker.tick(slot_to_roll)

        verdict = checker.get_final_verdict(slot_to_roll)
        assert verdict.is_correct is True
        assert verdict.asked_roll == 14
        assert verdict.speaker_slot == 0

    def test_wrong_student_answers(self):
        """Roll 14 is asked, but Roll 7 (slot 1) is speaking → is_correct=False."""
        tracker, checker = self._make_checker()
        slot_to_roll = {0: 14, 1: 7}
        checker.start(asked_roll=14)

        # Slot 1 (Roll 7) speaks, Slot 0 (Roll 14) silent
        speaking = [2, 18, 3, 17, 2, 19, 2, 18, 3, 17, 2, 19, 2, 18, 3, 17, 2, 19, 2, 18]
        silent   = [2.0] * 20

        for sp, si in zip(speaking, silent):
            lm_speak  = make_landmarks(lip_aperture_px=sp)
            lm_silent = make_landmarks(lip_aperture_px=si)
            tracker.update(1, lm_speak,  frame_h=480)  # slot 1 speaking
            tracker.update(0, lm_silent, frame_h=480)  # slot 0 silent
            checker.tick(slot_to_roll)

        verdict = checker.get_final_verdict(slot_to_roll)
        assert verdict.is_correct is False
        assert verdict.speaker_slot == 1
        assert verdict.speaker_roll == 7   # wrong student

    def test_no_speaker_detected(self):
        """Everyone silent — speaker_slot should be None."""
        tracker, checker = self._make_checker(threshold=0.01)
        slot_to_roll = {0: 14}
        checker.start(asked_roll=14)

        # All silent
        for _ in range(20):
            lm = make_landmarks(lip_aperture_px=2.0)
            tracker.update(0, lm, frame_h=480)
            checker.tick(slot_to_roll)

        verdict = checker.get_final_verdict(slot_to_roll)
        assert verdict.speaker_slot is None or not verdict.is_correct

    def test_verdict_has_confidence(self):
        tracker, checker = self._make_checker()
        slot_to_roll = {0: 14}
        checker.start(asked_roll=14)

        speaking = [2, 18, 3, 17, 2, 19, 2, 18, 3, 17, 2, 19, 2, 18, 3, 17, 2, 19, 2, 18]
        for sp in speaking:
            tracker.update(0, make_landmarks(lip_aperture_px=sp), frame_h=480)
            checker.tick(slot_to_roll)

        verdict = checker.get_final_verdict(slot_to_roll)
        assert 0.0 <= verdict.confidence <= 1.0

    def test_verdict_has_activity_scores(self):
        tracker, checker = self._make_checker()
        slot_to_roll = {0: 14, 1: 7}
        checker.start(asked_roll=14)

        for _ in range(15):
            tracker.update(0, make_landmarks(lip_aperture_px=2.0), frame_h=480)
            tracker.update(1, make_landmarks(lip_aperture_px=2.0), frame_h=480)
            checker.tick(slot_to_roll)

        verdict = checker.get_final_verdict(slot_to_roll)
        assert isinstance(verdict.activity_scores, dict)
